# Engineering Knowledge AI Agent Test

### 1. Describe differences between REST API, MCP in the context of AI.

**REST API** is a way for a client to communicate with a server over HTTP using standard methods such as GET, POST, PUT, and DELETE. It follows a contract that is agreed beforehand, which means requests must follow a certain format and the server returns responses in a fixed schema, although the data inside the response can change depending on the server state.

On the other hand, **MCP** is a standard way for LLM applications to connect to tools, resources, and prompts. The MCP server exposes its tools with names, descriptions, and JSON Schema inputs through JSON-RPC, and the client can discover them at runtime. The LLM then reads these descriptions and decides by itself which tool to call and with what arguments, while in REST API the developer has to hardcode which endpoint to call.

---

### 2. How REST API, MCP, can improve the AI use case.

**REST API** can be used to serve the model as an inference endpoint and to expose the AI agent through a standardized HTTP interface, so it can be integrated into existing systems such as web apps, mobile apps, or other services. It also allows the agent to call existing business APIs through function calling.

**MCP** can improve the AI use case because a tool only needs to be built once as an MCP server, and then it can be reused by any MCP-compatible host or agent without rewriting the integration code. New tools can be added without redeploying the agent, and access control can be centralized on the server side. However, MCP also adds risks such as prompt injection through tool output, so the server output should be treated as untrusted.

---

### 3. How do you ensure that your AI agent answers correctly?

- Use RAG with hybrid retrieval (BM25 and vector search) and a reranker. Require the model to cite its sources and refuse to answer when the retrieved context is insufficient
- Use structured output and validate it before using it
- Route deterministic tasks such as math or SQL to tools instead of the LLM
- Build a golden dataset of questions with expected answers and sources, then measure retrieval recall and answer faithfulness and correctness against it
- Re-run the evaluation every time the prompt, model, or chunking changes
- Add guardrails for input and output
- Trace every step of the agent for observability, and collect user feedback to add failed cases back into the evaluation dataset.

---

### 4. Describe what can you do with Docker / Containerize environment in the context of AI

By using a containerized environment we can reproduce the same environment, including the OS, Python, CUDA, and library versions, so the application behaves the same locally and in production. It can be used to serve the model with GPU passthrough, and to interconnect the agent with external tech stacks such as a vector DB, Redis, MCP servers, and observability through Docker Compose. Furthermore, since a containerized environment is isolated, it can be used as a sandbox to run LLM-generated code with no network, resource limits, and a read-only filesystem.

---

### 5. How do you finetune the LLM model from raw?

- Collect raw data from the domain, then clean it by removing duplicates, PII, and low-quality samples
- Use a stronger model to generate synthetic data only as augmentation, and filter its quality
- Format the data with the model's chat template and split it into training, validation, and test datasets
- Run supervised fine-tuning using LoRA or QLoRA and tune hyperparameters such as learning rate, epochs, and LoRA rank
- Optionally use DPO for preference tuning; Evaluate the results on the test dataset, compare them against the base model with prompting or RAG
