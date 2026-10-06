# utils/minio_utils.py

import json
from minio import Minio
from config.minio_config import minio_config
try:
    minio_client = Minio(
        endpoint=minio_config.endpoint,
        access_key=minio_config.access_key,
        secret_key=minio_config.secret_key,
        secure=False)
    # secure=False 是否启用HTTPS加密连接；False=用HTTP，True=用HTTPS；本地/内网部署一律写False
    if not minio_client.bucket_exists(minio_config.bucket_name):
        minio_client.make_bucket(minio_config.bucket_name)
    # 设置存储桶策略为 Public Read (只读权限开放给匿名用户)
    # 这样前端可以直接通过 URL 访问图片，而不需要预签名 URL
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{minio_config.bucket_name}/*"]
            }
        ]
    }
    # json.dumps(policy) —— 注意是 dumps（复数）：把字典变成 JSON 字符串
    # json.dump()（单数）是往文件里写的，这里用错会直接崩
    minio_client.set_bucket_policy(minio_config.bucket_name, json.dumps(policy))
except Exception as e:
    # f-string 前缀不能漏：少了 f，{e} 就只是三个普通字符，看不出错原因
    print(f"Minio init failed: {e}")
    minio_client = None

def get_minio_client():
    return minio_client