# Research Notes

Date: 2026-06-01

## Current Architecture Choices

- Keep a custom runtime for the first slices. It gives us full control over policy, audit logs, filesystem boundaries, and explicit fallback behavior while model-driven planning selects capabilities from schemas.
- Later, evaluate LangGraph for durable execution, checkpointing, human-in-the-loop interrupts, memory, replay, and failure recovery.
- For browser automation, evaluate Browser Use because it builds on Playwright and exposes web pages as agent-operable elements.
- For Windows OS control, prefer Microsoft UI Automation / accessibility-tree inspection before screenshot-only control.
- Treat OWASP LLM Top 10 risks, especially prompt injection and excessive agency, as product requirements rather than a later security pass.

## Sources Checked

- LangGraph persistence and human-in-the-loop docs: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph human-in-the-loop docs: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Browser Use repository: https://github.com/browser-use/browser-use
- Microsoft UI Automation overview: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications
- OpenAI Responses API reference: https://platform.openai.com/docs/api-reference/responses
- OpenAI Structured Outputs guide: https://platform.openai.com/docs/guides/structured-outputs

## Next Research Decisions

- Choose whether the planner becomes LangGraph-based in milestone 2 or remains custom until browser/OS tools exist.
- Compare local vector stores: SQLite FTS first, then LanceDB/Qdrant only when semantic memory requires embeddings.
- Define a prompt-injection test suite before adding browser and email tools.
