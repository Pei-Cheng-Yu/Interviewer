from app.core.agents.interviewer_agent.agent import build_interviewer_graph


def main():

    graph = build_interviewer_graph()

    # Get the graph structure and draw the mermaid string
    mermaid_code = graph.get_graph(xray=1).draw_mermaid()

    # Print the plain text code
    print(mermaid_code)


# FIX 2: This block is required to actually run the main function
if __name__ == "__main__":
    main()
