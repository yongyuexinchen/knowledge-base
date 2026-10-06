# processor/import_processor/nodes/node_pdf_to_md.py
import json
import shutil
import time
import zipfile
from pathlib import Path

import requests
from typing import Dict, List, Tuple

from config.mineru_config import mineru_config
from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError, ConfigurationError, \
    PdfConversionError
from processor.import_processor.state import ImportGraphState
# 注意：这里不能从 test/ 目录导入任何东西 —— test 是 Python 自带的包名，
# 自带的（正规包）优先级高于你的 test/（散装目录），import 必然失败。
# 计时变量直接在轮询循环里用 time.time() 生成，见 _step_2 里的 start_time。


class NodePDFToMD(BaseNode):
    """
    PDF 转 Markdown 节点（流水线第 ② 步）：把 PDF 变成纯文本。

    一句话：**吃一个 PDF 文件路径，吐一个 Markdown 文件路径**（不是内容本身）。

    ── 位置 ───────────────────────────────────────────────────────────
    只有入口点亮 is_pdf_read_enabled 时才执行；走 .md 分支会被直接跳过。

    ── 它要干的活 ─────────────────────────────────────────────────────
    不是简单抽文字，而是**还原版面结构**（本项目打算用 MinerU 这个工具）：
        · 识别标题层级 → 输出 # / ## / ###（后面按标题切分就靠它）
        · 识别表格     → 转成 Markdown 表格，保住行列关系
        · 抽离图片     → 存成独立文件，正文里插入 ![](路径) 引用
        · 去掉双栏/页眉页脚 → 否则正文被切碎、噪音混进来
    用 PyPDF2 那种纯文本抽取做不到这些 —— **这一步的质量决定整个 RAG 的上限**。

    ── 开工前要知道的两件事（已实测）──────────────────────────────────
      ① 依赖没装：.venv 里**没有 mineru**。开工前要 uv add "mineru[core]"，
         且 .env 里 MODELSCOPE_OFFLINE=1 意味着模型要提前离线下载好，
         否则第一次跑会报"离线模式下找不到模型"。
      ② 慢：解析几十页 PDF 可能要几分钟。同一份 PDF 重复导入时，
         应先检查产出是否已存在，别每次都重新解析（白烧 GPU 时间）。
    """

    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState):
        """
        调 MinerU 把 PDF 解析成 Markdown，落盘，把路径记进 state。

        输入（从 state 读的字段）：
            import_file_path : str
                哪来的：外部调用方（不是上一个节点写的）
                长什么样："D:/docs/某设备手册.pdf"
                什么时候有值：一开始就有
                怎么用：直接喂给 MinerU 当解析目标

        加工：
            1. 拿 import_file_path 指向的 PDF
            2. 调 MinerU 解析：还原标题/表格/图片
            3. 把 Markdown 正文**写到磁盘**
            4. 图片单独存文件，正文里插入相对路径引用
            5. 从原文件名算出 file_title（去掉扩展名）

        输出：
            建议返回（三个字段）：
                {"md_path": ".../xxx.md",        # MD 文件落在哪
                 "file_dir": ".../xxx/",         # 本次任务的目录（图片也在里面）
                 "file_title": "某设备手册"}      # 原文件名去掉扩展名
            谁接手：
                md_path     → ③ 去这个文件里找图片引用；④ 去读正文
                file_dir    → ③ 图片往哪存
                file_title  → ④ 当切片的来源标签

            ⚠️ 关键设计：MD 内容**不要**塞进 state，只存路径。
               一份 PDF 的 MD 可能几 MB，塞进全程在内存里传递的 state，
               每步快照都会变大，调试时打印 state 直接刷屏。
               **大东西传路径，小数据进 state。**
               ⚠️ 但这与 ③④ 的假设冲突（它们读的是 state["md_content"]）——
                  两种做法必须先定一种，见 docs/FLOW.md 第四节。
        """

        # 步骤1：校验PDF路径和输出目录
        pdf_path_obj, output_dir_obj = self._step_1_validate_paths(state)

        # 步骤2：上传PDF至MinerU并轮询解析结果
        zip_url = self._step_2_upload_and_poll(pdf_path_obj)

        # 步骤3：下载ZIP包并提取MD文件
        md_path = self._step_3_download_and_extract(zip_url, output_dir_obj, pdf_path_obj.stem)

        # 步骤4：读取md的内容
        # 注意：这里把正文整个读进 state（md_content）——
        # 与老注释"只存路径不存内容"相反，现在按 ③ node_md_img 的需要传内容
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 步骤5：更新state状态
        state["md_path"] = md_path
        state["md_content"] = md_content

        return state

    def _step_1_validate_paths(self,state:ImportGraphState):
        """
        步骤1：校验PDF文件路径和输出目录
        核心职责：参数非空校验 | 路径转换 | PDF文件有效性校验 | 输出目录自动创建
        返回：合法的PDF文件Path对象、输出目录Path对象
        异常：StateFieldError(参数缺失)、FileProcessingError(文件无效)
        """

        # 1、参数非空校验
        # pdf_path：由入口节点（node_entry）从 import_file_path 翻译而来
        pdf_path = state.get("pdf_path")
        if not pdf_path:
            raise StateFieldError(field_name='pdf_path',expected_type=str)

        # file_dir：解析结果往哪放。
        # 入口节点不写它，默认用 PDF 自己所在的目录（zip 包和解压结果都落在旁边）
        file_dir = state.get("file_dir") or str(Path(pdf_path).parent)

        # 2、转换为Path对象统一处理路径
        pdf_path_obj  = Path(pdf_path)
        file_dir_obj =  Path(file_dir)

        # 3、PDF文件有效性校验
        if not pdf_path_obj.exists():
            raise FileProcessingError(message=f"PDF文件{pdf_path_obj.name}不存在")

        # 4、确保输出目录存在，不存在则递归创建
        if not file_dir_obj.exists():
            self.logger.info(f"输出目录不存在，自动创建：{file_dir_obj.absolute()}")
            file_dir_obj.mkdir(parents=True,exist_ok=True)

        return pdf_path_obj,file_dir_obj

    def _step_2_upload_and_poll(self,pdf_path_obj:Path):
        """
        步骤2：上传PDF至MinerU并轮询解析任务状态
        核心流程：配置校验 → 获取上传链接 → 文件上传 → 任务轮询（直至完成/失败/超时）
        参数：pdf_path_obj-已校验的PDF Path对象
        返回：解析结果ZIP包下载链接full_zip_url
        异常：ConfigurationError(配置缺失)、PdfConversionError(请求/上传失败)、TimeoutError(任务超时)
        """
        # 1、配置文件校验（字段名必须和 MinerUConfig 里的一致：base_url_prod / api_token_prod）
        if not mineru_config.base_url_prod:
            raise ConfigurationError("MinerU配置缺失：请在 .env 文件中正确配置 MINERU_URL 参数")

        if not mineru_config.api_token_prod:
            raise ConfigurationError("MinerU配置缺失：请在 .env 文件中正确配置 MINERU_TOKEN 参数")
        # 2、从MinerU服务器获取上传链接
        token = mineru_config.api_token_prod
        url =  f"{mineru_config.base_url_prod}/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": pdf_path_obj.name}
            ],
            "model_version": "vlm"
        }
        # 获取上传url和任务的batch_id
        response = requests.post(url, headers=header, json=data)

        # 对响应结果进行校验
        # 先校验http状态
        if response.status_code != 200:
            raise PdfConversionError(message=f"获取上传链接响应失败：状态码：{response.status_code}，响应结果：{response}")

        # 校验业务码
        result = response.json()
        if result.get("code") != 0:
            raise PdfConversionError(f"获取上传链接失败：返回数据：{result}")

        # 获取响应结果
        signed_url = result["data"]["file_urls"][0]
        batch_id = result["data"]["batch_id"]

        # 3、文件上传
        with open(pdf_path_obj,"rb") as f:
            res_upload = requests.put(signed_url,data=f)
            if res_upload.status_code != 200:
                raise PdfConversionError(f"文件上传失败：状态码：{res_upload.status_code}，响应结果：{res_upload}")
            self.logger.info(f"文件上传成功！")

        # 4、批量获取任务结果
        poll_url = f"{mineru_config.base_url_prod}/extract-results/batch/{batch_id}"
        start_time = time.time()  # 记录开始时间
        timeout_seconds = 600  # 最大超时时间
        poll_interval = 3  # 轮询间隔时间
        self.logger.info(f"【任务轮询】最大超时：{timeout_seconds}s，batch_id：{batch_id}")
        while True:
            # 用上面定义的 start_time（本次轮询开始时刻）算已耗时，
            # 不能用 import 进来的全局变量 —— 那个是"程序启动那一刻"，永远不更新
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                raise TimeoutError(f"【任务轮询】超时！任务处理超{timeout_seconds}秒，batch_id：{batch_id}")
            # 发起轮询请求，短超时10秒，异常则重试
            try:
                res_poll = requests.get(url=poll_url,headers=header,timeout=10)
            except Exception as  e:
                self.logger.warning(f"【任务轮询】网络请求异常，{poll_interval}秒后重试：{str(e)}，bactch_id：{batch_id}")
                time.sleep(poll_interval)
                continue

            # 处理HTTP响应错误
            if res_poll.status_code != 200:
                raise PdfConversionError(f"【任务轮询】HTTP请求失败，状态码：{res_poll.status_code}，响应内容：{res_poll}")

            # 解析轮询结果，校验业务状态
            poll_data = res_poll.json()
            if poll_data["code"] != 0:
                raise PdfConversionError(f"【任务轮询】业务错误，返回数据：{poll_data}")

            extract_results = poll_data["data"]["extract_result"]
            # 获取结果
            result_item = extract_results[0]
            data_state = result_item["state"]

            # 状态为 done
            if data_state == "done":
                self.logger.info(f"【任务轮询】解析任务完成！总耗时{int(elapsed_time)}s，bactch_id：{batch_id}")
                full_zip_url = result_item["full_zip_url"]
                self.logger.info(f"【任务轮询】返回ZIP包下载链接：{full_zip_url}，bactch_id：{batch_id}")
                return full_zip_url
            elif data_state == "failed":
                err_msg = result_item.get("err_msg", "未知错误，无具体信息")
                raise PdfConversionError(f"【任务轮询】解析任务失败！batch_id：{batch_id}，错误信息：{err_msg}")
            else:
                self.logger.info(f"【任务轮询】处理中... 已耗时{int(elapsed_time)}s，状态：{data_state}， batch_id：{batch_id}")
                time.sleep(poll_interval)


    def _step_3_download_and_extract(self, zip_url: str, output_dir_obj: Path, pdf_stem: str) -> str:
        """
       步骤3：下载MinerU解析结果ZIP包并解压，提取目标MD文件
       核心流程：下载ZIP → 清理旧目录并解压 → 查找MD文件 → 重命名统一为PDF同名
       参数：zip_url-ZIP包下载链接；output_dir_obj-输出目录Path；pdf_stem-PDF无后缀纯名称
       返回：最终MD文件的字符串格式绝对路径
       异常：RuntimeError(下载失败)
       """

        # 1、下载ZIP包
        self.logger.info(f"【ZIP下载】开始下载ZIP包：{zip_url} ...")
        response = requests.get(zip_url)

        # 对响应结果进行校验
        if response.status_code != 200:
            raise RuntimeError(f"【ZIP下载】ZIP包下载失败：状态码：{response.status_code}，响应结果：{response}")

        # 拼接ZIP包保存路径并保存
        zip_save_path = output_dir_obj / f"{pdf_stem}_result.zip"
        with open(zip_save_path,'wb') as  f:
            f.write(response.content)
        self.logger.info(f"【ZIP下载】ZIP包下载成功：保存路径：{zip_save_path}")


        # 2. 如果目标文件夹已存在，先删除（确保环境干净）
        extract_target_dir = output_dir_obj / pdf_stem
        if extract_target_dir.exists():
            shutil.rmtree(extract_target_dir)
        self.logger.info(f"【ZIP解压】已清空旧的解压目录：{extract_target_dir}")
        # 3、创建解压目录
        extract_target_dir.mkdir(parents=True,exist_ok=True)

        # 4、解压
        self.logger.info(f"【ZIP解压】开始解压ZIP包：{output_dir_obj} ...")
        with zipfile.ZipFile(zip_save_path, "r") as zip_file_obj:
            zip_file_obj.extractall(extract_target_dir)

        # 5、重命名
        self.logger.info(f"【MD重命名】找到MinerU生成的full.md文件")
        target_md_file = extract_target_dir / "full.md"
        self.logger.info(f"【MD重命名】开始将full.md文件进行重命名")
        new_md_path = target_md_file.with_name(f"{pdf_stem}.md")
        target_md_file.rename(new_md_path)
        self.logger.info(f"【MD重命名】重命名成功，文件名：{pdf_stem}.md")
        return str(new_md_path.absolute())

