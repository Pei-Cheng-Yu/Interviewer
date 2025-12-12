from langchain_ollama import ChatOllama



def get_llm(temperature: int = 0):
    """
    Returns the configured LLM instance.
    """
    
    llm = ChatOllama(
        model="gemma3:4b",
        temperature=temperature,
    )
    
    return llm