import sys
import traceback

try:
    from langchain_community.vectorstores import FAISS
    print("SUCCESS: FAISS imported.")
except ImportError as e:
    print(f"FAILED TO IMPORT: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"UNEXPECTED ERROR: {e}")
    traceback.print_exc()
