from langchain_ollama import ChatOllama


llm = ChatOllama(
    model="gemma3:4b",
    temperature=0,
)

def get_llm():
    """
    Returns the configured LLM instance.
    """
    return llm