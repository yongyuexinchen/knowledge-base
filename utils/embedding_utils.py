from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from config.embedding_config import embedding_config


_bge_m3_ef = None

def get_bge_m3_ef():
    """
    获取全局单例的BGEM3EmbeddingFunction对象
    :return:  BGEM3EmbeddingFunction对象
    """
    global _bge_m3_ef
    if _bge_m3_ef is not None:
        return _bge_m3_ef

    model_name = embedding_config.bge_m3_path
    device = embedding_config.bge_device
    use_fp16 = embedding_config.bge_fp16

    _bge_m3_ef = BGEM3EmbeddingFunction(
        model_name=model_name,
        device=device,
        use_fp16=use_fp16
    )

    return _bge_m3_ef


def generate_embeddings(texts):
    """
    为文本生成向量嵌入
    :param texts: 要生成嵌入的文本列表
    :return: 包含dense和sparse向量的字典
    """

    model = get_bge_m3_ef()
    embeddings = model.encode_documents(texts)

    processed_sparse = []
    for i in range(len(texts)):

        sparse_obj = embeddings["sparse"]
        sparse_indices = sparse_obj.indices[
            sparse_obj.indptr[i]:sparse_obj.indptr[i + 1]].tolist()

        sparse_data = sparse_obj.data[
            sparse_obj.indptr[i]:sparse_obj.indptr[i + 1]].tolist()

        sparse_dict = {k: v for k, v in zip(sparse_indices, sparse_data)}
        processed_sparse.append(sparse_dict)

    return {
        "dense": [emb.tolist() for emb in embeddings["dense"]],
        "sparse": processed_sparse
    }
