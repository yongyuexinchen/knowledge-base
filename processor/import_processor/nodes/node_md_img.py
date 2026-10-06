# processor/import_processor/nodes/node_md_img.py
import base64
import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Tuple, List, Dict, Deque
import json
from langchain_openai import ChatOpenAI
from minio import Minio
from minio.deleteobjects import DeleteObject

from config.lm_config import lm_config
from config.minio_config import minio_config

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError
from processor.import_processor.state import ImportGraphState
from utils.minio_utils import get_minio_client


# 💡 小知识：下面类的说明文字用了 r""" 开头（r = raw，原样字符串）。
#    因为里面要写正则表达式 r'!\[.*?\]\((.*?)\)'，含反斜杠。
#    普通字符串里 \ 是"转义符"，碰到 \[ 这种不认识的组合会报警告。
#    加了 r，所有 \ 都按字面理解。写正则、写 Windows 路径（C:\Users\...）都记得加 r。
class NodeMDImg(BaseNode):
    r"""
    Markdown 图片处理节点（流水线第 ③ 步）：让模型"看懂"图。

    一句话：**把正文里的 ![](图片路径) 引用，换成一段文字描述** ——
    因为后面的切分和向量化只认识文字，不认识图。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ③ 步，是两条支路的汇合点：
        PDF 分支：① → ② → ③
        MD  分支：① →（跳过 ②）→ ③

    ── 为什么要做这一步 ───────────────────────────────────────────────
    一份 PDF 的关键信息常常挂在图表上（流程图、数据曲线）。
    只切文字，这些内容等于凭空消失。

    ── 用到 config 里的三个参数 ───────────────────────────────────────
        img_content_length = 200   给模型描述图片时，附带图片周边文字的长度
                                   （单看图容易认错场景，带上下文才贴题）
        requests_per_minute = 15   调看图模型的频率上限（供应商有限流）
                                   ⚠️ 50 张图要跑 3 分多钟，是耗时大户
        image_extensions           判断扫到的是不是真图片，过滤链接、附件
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        r"""
        扫出正文里的图片引用，逐张调模型生成描述，再把描述写回正文。
        （这段说明文字也带了 r 前缀，因为下面要写正则，含反斜杠。）

        输入（从 state 读的字段）：
            md_content : str
                哪来的：按当前规划是 ② 产出的正文
                       ⚠️ 但 ② 的注释说"只存路径不存内容"，两种做法冲突，
                          必须先定一种（见 docs/FLOW.md 第四节）
                长什么样："# 第一章\n\n如图所示：![](images/fig1.png)\n\n..."
            或者 md_path : str  ← 如果定的是"只传路径"，就用它去读文件
            file_dir : str      ← 图片文件在哪个目录（② 给的）

        加工：
            1. 用正则扫出所有图片引用：r'!\[.*?\]\((.*?)\)'
            2. 逐个读图（本地路径，或从 MinIO 下载）
            3. 截取图片周边 200 个字符当上下文
            4. 调看图模型（cfg.vl_model）："这张图里画的是什么？"
            5. 把描述**替换**掉原来的图片引用：
                   ![](fig1.png)  →  【图片描述】这是一张收益率曲线……
               为什么是"替换"而不是"追加到文末"？
               state 里没有单独的"图片描述"字段，说明设计就是就地替换；
               好处是切分时描述会落在图片原来的位置，上下文连贯。
            6. 顺便把图片上传 MinIO，正文里的路径换成对象 key

        输出：
            建议返回：{"md_content": 改好的正文}
            谁接手：④ —— 它切分用的就是 md_content
            ⚠️ 目前返回的是完整 state，和"只返回改动字段"的约定不一致。

        副作用（三件要知道的事）：
            ① 会往 MinIO 上传图片（或往 file_dir 写文件）
            ② 会调外部付费 API，有频率限制
            ③ 这一步不做的话，"images/xxx.png" 这种本地临时路径会残留在
               正文里，切分后全是死链 —— 检索命中了也没法展示图片。
        """

        # ⚠️ 空实现占位。
        # 期待的实现骨架：
        #     md = state["md_content"]
        #     for img_ref in re.findall(r'!\[.*?\]\((.*?)\)', md):
        #         desc = call_vl_model(img_ref, context, self.config)
        #         md = md.replace(f"![]({img_ref})", f"【图片描述】{desc}")
        #     return {"md_content": md}     # ← 只返回自己改动的字段


        """
        MD文件图片处理核心节点
        核心流程：
        1. 获取MD内容、文件路径、图片文件夹路径
        2. 扫描图片文件夹，筛选MD中实际引用的支持格式图片
        3. 调用多模态大模型为图片生成内容摘要
        4. 将图片上传至MinIO，替换MD中本地图片路径为MinIO访问URL，并填充图片摘要
        5. 备份原MD文件，保存处理后的新MD文件并更新状态

        :param state: md_path、md_content
        :return: md_path、md_content
        """

        # 步骤1：初始化数据，获取MD核心信息
        md_content, md_path_obj, images_dir = self._step_1_get_content(state)
        if not images_dir.exists():
            self.logger.info("无图片文件夹，跳过图片处理")
            return state

        # 步骤2：扫描并筛选MD中引用的图片
        target_images= self._step_2_scan_images(md_content, images_dir)
        if not target_images:
            self.logger.info("未检测到MD中引用了图片，跳过图片处理")
            return state
        # 步骤3：调用多模态大模型生成图片摘要
        summaries = self._step_3_generate_summaries(md_path_obj.stem, target_images)

        # 步骤4：上传图片至MinIO，替换MD图片路径并填充摘要
        new_md_content = self._step_4_upload_and_replace(md_path_obj.stem, target_images, summaries, md_content)
        # 步骤5：备份并保存新MD文件
        new_md_file_name = self._step_5_backup_new_md_file(state['md_path'], new_md_content)
        # 步骤6：更新state状态值
        state["md_content"] = new_md_content
        state["md_path"] = new_md_file_name
        return state

    def _step_5_backup_new_md_file(self, origin_md_path: str, md_content: str) -> str:
        """
        步骤5：将处理后的MD内容保存为新文件（原文件不变，避免数据丢失）
        新文件命名规则：原文件名 + _new.md（如test.md → test_new.md）
        :param origin_md_path: 原始MD文件完整路径
        :param md_content: 处理后的新MD内容
        :return: 新MD文件的完整路径
        """
        # 构造新文件路径：替换原后缀为 _new.md
        new_md_file_name = os.path.splitext(origin_md_path)[0] + "_new.md"

        # 写入新MD内容（覆盖写入，若文件已存在则更新）
        with open(new_md_file_name, "w", encoding="utf-8") as f:
            f.write(md_content)

        self.logger.info(f"处理后MD文件已保存，新文件路径：{new_md_file_name}")

        return new_md_file_name



    def _step_4_upload_and_replace(self, doc_stem: str, target_images: List[Tuple[str, str, Tuple[str, str]]],
                                   summaries: Dict[str, str], md_content: str) -> str:
        """
        步骤 4: 上传图片并合并信息，然后替换 Markdown 中的内容。

        流程：
        1. 确定 MinIO 上的上传目录（按文档名隔离）。
        2. 清理该目录下的旧数据。
        3. 批量上传图片。
        4. 合并"图片摘要"和"图片URL"。
        5. 替换 Markdown 文本中的图片引用。
        :param doc_stem: 文档文件名（不含后缀），作为MinIO上传子目录名（按文档隔离）
        :param target_images: 待处理图片列表，元素为(图片文件名, 图片完整路径, 图片上下文)
        :param summaries: 图片摘要字典，键：图片文件名，值：内容摘要
        :param md_content: 原始MD文件内容
        :return: 图片引用替换后的新MD内容
        """
        # 获取MinIO客户端
        minio_client = get_minio_client()

        # 构造上传目录，去除文件名中的空格
        minio_img_dir = minio_config.img_dir
        upload_dir = f"{minio_img_dir}/{doc_stem}".replace(" ", "")

        # 步骤1：清理该文档对应的MinIO旧目录
        self._clean_minio_directory(minio_client, upload_dir)

        # 步骤2：批量上传图片至MinIO，获取URL映射
        urls = self._upload_images_batch(minio_client, upload_dir, target_images)

        # 步骤3：合并图片摘要和URL，过滤上传失败的图片
        image_info = self._merge_summary_and_url(summaries, urls)

        # 步骤4：替换MD内容中的本地图片引用为MinIO远程引用
        md_content = self._process_md_file(md_content, image_info)

        return md_content

    def _process_md_file(self, md_content: str, image_info: Dict[str, Tuple[str, str]]) -> str:
        """
        核心功能：替换MD内容中的本地图片引用为MinIO远程引用
        替换规则：![原描述](本地路径) → ![图片摘要](MinIO访问URL)
        :param md_content: 原始MD文件内容
        :param image_info: 合并后的图片信息字典，键：图片文件名，值：(摘要, URL)
        :return: 替换后的新MD内容
        """
        # 遍历 image_info 字典的每一项：key=图片文件名，value=(摘要, 新URL)
        for image_file, (summary, new_url) in image_info.items():
            # 正则匹配MD图片标签，忽略大小写
            # 正则规则：![任意描述](任意路径+图片文件名+任意后缀)
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
            # 替换匹配内容：使用新摘要作为图片描述，新URL作为图片路径
            md_content = pattern.sub(lambda m: f"![{summary}]({new_url})", md_content)

        self.logger.info(f"MD文件图片引用替换完成，共替换{len(image_info)}处图片引用")
        # 别忘了返回改好的内容 —— 不返回的话调用方拿到 None
        return md_content

    def _clean_minio_directory(self, minio_client: Minio, prefix: str) -> None:
        """
        幂等性清理：上传前先删除 MinIO 中指定目录下的旧文件。
        防止重名文件导致的内容混淆或垃圾堆积。
        :param minio_client: 初始化完成的MinIO客户端对象
        :param prefix: MinIO目录前缀（要清理的目录路径）
        """
        try:
            objects_to_delete = minio_client.list_objects(minio_config.bucket_name, prefix=prefix, recursive=True)
            # 构造删除列表
            delete_list = [DeleteObject(obj.object_name) for obj in objects_to_delete]
            if delete_list:
                # 删除用哪个桶必须和上面列出来的一致（都是 minio_config.bucket_name）
                errors = minio_client.remove_objects(minio_config.bucket_name, delete_list)
                # 遍历变量别和列表同名：for error in errors，否则第二次循环就找不到列表了
                for error in errors:
                    self.logger.error(f"删除失败：{error}")
        except Exception as e:
            self.logger.error(f"清理minio目录失败：{e}")


    def _merge_summary_and_url(self, summaries: Dict[str, str], urls: Dict[str, str]) -> Dict[str, Tuple[str, str]]:
        """
        合并图片摘要字典和URL字典，过滤掉上传失败无URL的图片
        :param summaries: 图片摘要字典，键：图片文件名，值：图片内容摘要
        :param urls: 图片URL字典，键：图片文件名，值：MinIO访问URL
        :return: 合并后的图片信息字典，键：图片文件名，值：(摘要, URL)元组
        """
        image_info = {}
        for image_file, summary in summaries.items():
            if url := urls.get(image_file):
                image_info[image_file] = (summary, url)
        # return 写在 for 外面：写在里面只会返回第一张就退出
        return image_info



    def _upload_images_batch(self, minio_client: Minio, upload_dir: str, target_images: List[Tuple]) -> Dict[str, str]:
        """
        批量上传待处理图片至MinIO，返回图片文件名与访问URL的映射关系
        :param minio_client: 初始化完成的MinIO客户端对象
        :param upload_dir: MinIO上传根目录
        :param target_images: 待处理图片列表，元素为(图片文件名, 图片完整路径, 图片上下文)
        :return: 图片URL字典，键：图片文件名，值：MinIO访问URL
        """
        urls = {}
        for img_file, img_path, _ in target_images:
            # 每张图片在MinIO里的对象名：上传目录/文件名（去空格防路径解析错误）
            object_name = f"{upload_dir}/{img_file}".replace(" ", "")
            url = self._get_minio_image_url(minio_client, img_path, object_name)
            if url:
                urls[img_file] = url
        return urls

    def _step_3_generate_summaries(self, doc_stem: str, target_images: List[Tuple[str, str, Tuple[str, str]]]) -> Dict[str, str]:
        """
        步骤3：批量为待处理图片生成内容摘要，带API速率限制防止触发大模型限流
        :param doc_stem: 文档文件名（不含后缀），作为大模型prompt上下文
        :return: 图片摘要字典，键：图片文件名，值：图片内容摘要
        """
        summaries = {}
        # 1、外部初始化双端队列，用于API速率限制，跨循环复用
        request_deque = deque()

        # 2、循环处理图片
        for img_file, image_path, context in target_images:
            # 2.1、速率限制（上限从配置读：requests_per_minute=15）
            self._apply_api_rate_limit(request_deque, max_requests=self.config.requests_per_minute)
            # 2.2、调用大模型生成图片摘要
            summaries[img_file] = self._summarize_image(image_path, root_folder=doc_stem, image_content=context)

        # return 必须在 for 外面 —— 写在循环里只会返回第一张图的摘要就提前退出
        return summaries

    def _summarize_image(self, image_path: str, root_folder: str, image_content: Tuple[str, str]) -> str:
        """
        调用多模态大模型总结图片内容。

        参数：
        - image_path: 图片本地路径。
        - root_folder: 文档所属文件夹名（提供更多上下文）。
        - image_content: 图片在文档中的上下文 (前文, 后文)。
        """
        with open(image_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")

        try:
            chat_model = ChatOpenAI(
                model=lm_config.vl_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""这是"{root_folder}"文件中的一张图片，图片上文部分为"{image_content[0]}"，下文部分为"{image_content[1]}"，请用中文简要总结这张图片的内容，用于 Markdown 图片标题。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            response = chat_model.invoke(messages)
            return response.content.strip().replace("\n", "")

        except Exception as e:
            self.logger.error(f"图像总结失败：{image_path}, 错误{e}")
            return "图片描述"


    def _apply_api_rate_limit(
            self,
            request_times: Deque[float],
            max_requests: int,
            window_seconds: int = 60
    ) -> None:
        """
        通用滑动窗口API速率限制器
        核心逻辑：维护请求时间戳双端队列，窗口内请求数超上限则自动等待，防止触发第三方API限流
        :param request_times: 存储请求时间戳的双端队列，需外部初始化，跨调用复用
        :param max_requests: 速率限制窗口内的最大允许请求次数
        :param window_seconds: 速率限制滑动窗口时长，默认60秒（1分钟）
        :return: None，超出限制时会阻塞等待
        """
        current_time = time.time()

        # 1. 清理滑动窗口外的过期请求时间戳，保证队列仅存窗口内的
        while request_times and current_time - request_times[0] >= window_seconds:
            request_times.popleft()

        # 2. 窗口内请求数达上限，计算并阻塞等待剩余时间
        if len(request_times) >= max_requests:
            sleep_duration = window_seconds - (current_time - request_times[0])
            if sleep_duration > 0:
                self.logger.info(
                    f"触发API速率限制，窗口{window_seconds}秒内最多{max_requests}次，需等待：{sleep_duration:.2f} 秒")
                time.sleep(sleep_duration)
                # 等待后更新当前时间，重新清理过期请求（避免等待期间有请求过期）
                current_time = time.time()
                while request_times and current_time - request_times[0] >= window_seconds:
                    request_times.popleft()

        # 3. 记录当前请求时间戳，加入滑动窗口队列
        request_times.append(current_time)


    def _step_2_scan_images(self, md_content: str, images_dir: Path) -> List[Tuple[str, str, Tuple[str, str]]]:
        """
        扫描图片文件夹，过滤出「支持格式+MD中实际引用」的图片，组装处理元数据
        :param md_content: MD文件完整内容
        :param images_dir: 图片文件夹路径对象
        :return: 待处理图片列表，每个元素为(图片文件名, 图片完整路径, 图片上下文)元组
        """
        # 1. 定义待处理图片列表
        target_images = []

        # 2. 遍历图片文件夹
        for image_file in os.listdir(images_dir):

            # 2.1 过滤无效后缀
            file_ext = os.path.splitext(image_file)[1].lower()
            if file_ext not in self.config.image_extensions:
                self.logger.warning(f"图片格式不支持，跳过：{image_file}")
                continue

            # 1.2 组装图片完整路径并转成字符串
            img_path = str(images_dir / image_file)

            # 1.3 查找图片在MD中的引用上下文
            context = self._find_image_in_md(md_content,image_file)

            # 过滤MD中未引用的图片
            if not context:
                self.logger.warning(f"图片未在MD中引用，跳过处理：{image_file}")
                continue

            # 1.4 组装待处理图片元数据，取第一个匹配的图片上下文
            target_images.append((image_file, img_path, context))

        return target_images

    def _step_1_get_content(self, state: ImportGraphState) -> Tuple[str, Path, Path]:
        """
        从全局状态中提取并初始化MD处理所需核心数据
        :param state: 流程全局状态对象
        :return: 元组(MD文件内容, MD文件路径, 图片文件夹路径)
        :raise FileProcessingError: 当状态中无有效MD文件路径时抛出
        """
        # 1、参数非空校验
        md_path = state.get("md_path")
        if not md_path:
            raise StateFieldError(field_name='md_path', expected_type=str)

        # 2、路径转换
        md_path_obj = Path(md_path)

        # 3、检查PDF文件的有效性
        if not md_path_obj.exists():
            raise FileProcessingError(message=f"MD文件{md_path_obj.name}不存在")
        # 4、获取md_content（② 节点读文件后写进 state 的正文）
        # 用 .get 而不是 state["md_content"]：字段缺失时 .get 返回 None，
        # 下面的 if 能给出明确的报错；直接 [] 会抛裸 KeyError，看不出缺什么
        md_content = state.get("md_content")
        if not md_content:
            raise StateFieldError(field_name='md_content', expected_type=str)

        # 5、组装图片文件夹路径：图片文件夹固定为MD文件同级的images目录
        images_dir = md_path_obj.parent / "images"

        return  md_content,md_path_obj, images_dir



    def _find_image_in_md(self, md_content: str, image_file: str, context_len: int = 100) -> Tuple[str, str]:
        """
        查找MD内容中指定图片的所有引用位置，并返回每个位置的上下文文本
        :param md_content: MD文件完整内容
        :param image_file: 图片文件名（含后缀）
        :param context_len: 上下文截取长度，默认前后各100字符
        :return: 每个图片的(上文, 下文)元组，无匹配则返回None
        """

        # 1、定义正则表达式
        # ![描述](images/文件名.扩展名)
        # r"字符串"：不要将其中的特殊符号进行转义
        # re.escape 转义图片文件名中的特殊字符，避免正则语法错误
        # .* 贪婪匹配 .*? 非贪婪匹配
        pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")

        # 2、找到1个匹配项即返回
        match = pattern.search(md_content)
        if not match:
            return  None #没找到

        # 3、截取匹配位置的上文和下文（防止索引越界）
        start, end = match.span()
        pre_text = md_content[max(0,start - context_len):start]
        post_text = md_content[end:min(len(md_content), end + context_len)]
        # 4、返回上下文元组
        return pre_text, post_text








    def _get_minio_image_url(self, minio_client: Minio, local_path: str, object_name: str) -> str:
        """
        上传单张图片到MinIO并返回可访问的URL
        :param minio_client: 初始化完成的MinIO客户端对象
        :param local_path: 图片本地完整路径
        :param object_name: 图片在MinIO里的对象名
        :return: 成功返回访问URL字符串，失败返回None（调用方决定跳过还是重试）
        """
        try:
            # 上传本地文件至MinIO（fput_object：按文件路径上传，适合大文件）
            minio_client.fput_object(
                bucket_name=minio_config.bucket_name,
                object_name=object_name,
                file_path=local_path,
                # 多后缀文件仅拆分最后一个：test.tar.gz 拆成 ("test.tar", ".gz")
                content_type=f"image/{os.path.splitext(local_path)[1][1:]}"
            )

            # 处理路径特殊字符，避免URL解析错误
            object_name = object_name.replace("\\", "%5C")

            # 构造MinIO基础访问URL
            base_url = f"http://{minio_config.endpoint}/{minio_config.bucket_name}"

            return f"{base_url}/{object_name}"

        except Exception as e:
            self.logger.error(f"图片上传MinIO失败：{local_path}，错误信息：{str(e)}")
            return None





if __name__ == "__main__":
    setup_logging()

    md_path = r"E:\doc\hak180产品安全手册\hak180产品安全手册.md"
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    init_state = {
        "md_path": md_path,
        "md_content": md_content
    }

    # 执行核心处理流程
    node_md_img = NodeMDImg()
    result = node_md_img(init_state)

    logging.getLogger().info(json.dumps(result, ensure_ascii=False, indent=4))
