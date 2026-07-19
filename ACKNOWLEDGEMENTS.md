# Acknowledgements

This project follows common patterns from the broader LLM evaluation ecosystem: versioned datasets, model adapters, deterministic harnesses, structured judging, safety gates, and machine-readable reports.

No third-party benchmark source code is vendored in this repository. Runtime dependencies are declared in `pyproject.toml` and pinned for production use in `requirements.lock`.

Useful related categories of work include LLM evaluation harnesses, automated red-team tools, prompt-injection test suites, model-judge pipelines, and safety regression gates. These ideas informed the project shape without requiring copied implementation code.
