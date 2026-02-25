import traceback

try:
    from langchain_community.vectorstores import FAISS
    print("SUCCESS")
except Exception as e:
    with open("function_test/test_rag/true_error.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print("FAILED, check true_error.txt")
