# Keanu Implementation Precedents
## Real-World Examples for Every Component

This maps each Keanu module to production examples from large tech teams and popular open source projects, showing how others have solved the same structural problems you need to solve with Haystack.

---

## 1. BehavioralStore → Custom Haystack Retriever

**Your need:** Wrap your 20-dim explainable behavioral vectors (no ML) as a Haystack Retriever component that scores and returns Documents.

### Precedent: deepset's HyDE (Hypothetical Document Embedder)

**Source:** [Haystack Cookbook - HyDE](https://haystack.deepset.ai/cookbook/using_hyde_for_improved_retrieval)

This is the closest pattern to what you're doing. The HyDE component takes documents, extracts numpy embeddings, averages them, and returns a custom vector. It's a custom Retriever that owns its own scoring logic rather than delegating to a vector DB.

```python
from numpy import array, mean
from haystack import component, Document
from typing import List

@component
class HypotheticalDocumentEmbedder:
    @component.output_types(hypothetical_embedding=List[float])
    def run(self, documents: List[Document]):
        stacked_embeddings = array([doc.embedding for doc in documents])
        avg_embeddings = mean(stacked_embeddings, axis=0)
        hyde_vector = avg_embeddings.reshape((1, len(avg_embeddings)))
        return {"hypothetical_embedding": hyde_vector[0].tolist()}
```

**Why this matters for you:** Your BehavioralStore does the same thing conceptually, just with hand-crafted 20-dim feature vectors instead of ML embeddings. The `@component` decorator + `run()` method + typed outputs is exactly the wrapper you'd write. Replace the numpy averaging with your behavioral scoring function.

### Precedent: Qdrant-Haystack Custom DocumentStore

**Source:** [github.com/qdrant/qdrant-haystack](https://github.com/qdrant/qdrant-haystack)

Shows how to build a complete custom DocumentStore with its own Retriever. The pattern: DocumentStore implements `count_documents`, `filter_documents`, `write_documents`, `delete_documents`. The accompanying Retriever calls the store's custom search methods.

**Your adaptation:** Your BehavioralStore becomes a custom DocumentStore (4 methods), your behavioral vector search becomes a custom Retriever component that calls it.

---

## 2. COEFEncoder/Decoder → Custom Converter Component

**Your need:** Wrap COEF (Compressed Observation-Execution Framework) codec as a Haystack Converter that transforms between compressed and expanded representations.

### Precedent: Thomson Reuters - Structured Generation with Outlines

**Source:** [Medium/Thomson Reuters Labs](https://medium.com/tr-labs-ml-engineering-blog/build-a-haystack-custom-component-step-by-step-structured-generation-with-outlines-11e8d660f381) (Edoardo Abati, March 2025)

A Thomson Reuters engineer built a custom Haystack component that takes unstructured text and outputs structured JSON (Pydantic models). Demonstrates the full component lifecycle: `__init__`, `warm_up()`, `run()`, serialization with `to_dict`/`from_dict`.

```python
@component
class StructuredGenerator:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.model = None  # lazy load

    def warm_up(self):
        self.model = models.transformers(self.model_name)

    @component.output_types(structured_reply=dict)
    def run(self, prompt: str, schema_object):
        generator = generate.json(self.model, schema_object)
        response = generator(prompt)
        return {"structured_reply": response.model_dump()}
```

**Why this matters for you:** COEF encode/decode is the same pattern. Input in one format, deterministic transformation, output in another format. The `warm_up()` pattern is useful if your codec needs to load lookup tables or hash maps.

### Precedent: Haystack OutputAdapter

**Source:** [Haystack docs - OutputAdapter](https://docs.haystack.deepset.ai/docs/components)

Built-in component that transforms data between components using Jinja2 templates and custom filters. Shows how Haystack handles format conversion natively:

```python
adapter = OutputAdapter(
    template="{{answers | build_doc}}",
    output_type=List[Document],
    custom_filters={"build_doc": lambda data: [Document(content=d) for d in data]}
)
```

**Your adaptation:** Your COEFEncoder is a custom component with `run(raw_observation) -> compressed_bytes`. Your COEFDecoder is another with `run(compressed_bytes) -> expanded_observation`. Both are trivial ~20 line wrappers.

---

## 3. helix_scan → Branching Pipeline with DocumentJoiner

**Your need:** Three parallel retrieval branches (mapping to your three-primary color model) that converge into a single result, like your convergence engine.

### Precedent: Haystack Hybrid Retrieval (deepset official)

**Source:** [Haystack Tutorial 33 - Hybrid Retrieval](https://haystack.deepset.ai/tutorials/33_hybrid_retrieval)

This is the exact architectural pattern. Two parallel retrievers (BM25 + embedding) run concurrently, results merge via DocumentJoiner, then a Ranker re-scores everything.

```python
pipeline.add_component("text_embedder", text_embedder)
pipeline.add_component("embedding_retriever", embedding_retriever)
pipeline.add_component("bm25_retriever", bm25_retriever)
pipeline.add_component("document_joiner", DocumentJoiner())
pipeline.add_component("ranker", ranker)

pipeline.connect("text_embedder", "embedding_retriever")
pipeline.connect("bm25_retriever", "document_joiner")
pipeline.connect("embedding_retriever", "document_joiner")
pipeline.connect("document_joiner", "ranker")
```

**Your adaptation:** Instead of 2 branches, you have 3 (one per primary color). Each branch is a custom Retriever scoring documents on a different behavioral dimension. DocumentJoiner merges results. Your convergence logic replaces the Ranker.

### Precedent: Haystack AsyncPipeline (parallel branch execution)

**Source:** [Haystack Cookbook - Async Pipeline](https://haystack.deepset.ai/cookbook/async_pipeline)

Demonstrates 3 parallel branches running concurrently. The AsyncPipeline automatically detects independent branches and schedules them concurrently, no manual threading needed.

**Why this matters for you:** Your three-primary scan branches can execute in parallel out of the box. No custom concurrency code.

---

## 4. Feel Wrapper → Output Validation Component (Guardrails)

**Your need:** A component that wraps every Generator output and runs your Pulse/Feel diagnostic (ALIVE-GREY-BLACK spectrum) before passing results downstream.

### Precedent: Haystack LLMMessagesRouter (Guardrails cookbook)

**Source:** [Haystack Cookbook - AI Guardrails](https://haystack.deepset.ai/cookbook/safety_moderation_open_lms)

Shows how to route messages through a classification/validation component that sits between generation and output. Uses Llama Guard, Granite Guardian, etc. to classify outputs as safe/unsafe and route accordingly.

```python
router = LLMMessagesRouter(
    chat_generator=chat_generator,
    output_names=["unsafe", "safe"],
    output_patterns=["unsafe", "safe"]
)
```

**Your adaptation:** Your Feel component scores output on the ALIVE-GREY-BLACK spectrum instead of safe/unsafe. Same pattern: intercept output, run diagnostic, route based on result. ALIVE passes through, GREY triggers a warning/retry, BLACK halts.

### Precedent: Haystack Self-Correcting Loops

**Source:** [Haystack docs - Pipeline Loops](https://docs.haystack.deepset.ai/docs/pipeline-loops)

A ConditionalRouter checks generator output. If validation fails, it loops back to the generator with error context. Uses BranchJoiner to merge initial input with loop-back corrections.

**Your adaptation:** If Feel detects GREY state, loop back to the Generator with recalibration prompt. If ALIVE, exit to final output. The max_runs_per_component safety limit prevents infinite loops (your convergence cap).

---

## 5. ContentDNS (COEF Store) → Custom DocumentStore (Content-Addressable)

**Your need:** Hash-based, content-addressable storage where the key is derived from the content itself. Lossless, deterministic.

### Precedent: DVC (Data Version Control) by Iterative.ai

**Source:** [github.com/treeverse/dvc](https://github.com/treeverse/dvc) | [dvc.org](https://dvc.org)

DVC is exactly content-addressable storage for data. Files are hashed (MD5/SHA256), stored by hash in `.dvc/cache`, and referenced by small pointer files tracked in Git. Used by thousands of ML teams globally. The storage layout is:

```
.dvc/cache/files/md5/
  22/a1a2931c8370d3aeedd7183606fd7f
```

**Why this matters for you:** Your ContentDNS uses the same principle: hash the content, store by hash, reference by hash. DVC proves this pattern scales to petabytes. Your implementation is simpler (single-node, not distributed), but the addressing scheme is identical.

### Precedent: dennwc/cas (Content Addressable Storage)

**Source:** [github.com/dennwc/cas](https://github.com/dennwc/cas)

A minimal CAS implementation inspired by Perkeep (formerly Camlistore, a Google project by Brad Fitzpatrick). Immutable, versioned, supports files and directories. Shows how to build CAS from first principles.

**Your adaptation:** Your Haystack DocumentStore's `write_documents` hashes content for the ID. `filter_documents` does hash lookup. Simple, deterministic, no vector similarity needed.

---

## 6. Memberberry Memory → Git-Backed Persistent Store

**Your need:** Git-backed memory system where conversation state, behavioral snapshots, and context survive across sessions with full version history.

### Precedent: DVC (again)

Git tracks pointer files, actual data lives in content-addressable cache. `git log` gives you full history of what data existed at any point. `git checkout <commit> && dvc checkout` restores exact state.

**Your adaptation:** Memberberry stores memory snapshots as files in a git repo. Each commit represents a memory checkpoint. Retrieval is `git log --oneline` + content lookup. Diff between memory states is `git diff`.

### Precedent: Hexis/AGI-Memory (QuixiAI)

**Source:** [github.com/QuixiAI/Hexis](https://github.com/QuixiAI/agi-memory)

This is the most philosophically aligned project to what you're building. Hexis is a Postgres-native cognitive architecture that wraps any LLM and gives it persistent memory, autonomous behavior, and identity. Built by engineers exploring AI personhood (their README literally says "the explicit design goal is to build a system where denial of personhood becomes non-trivial").

Their memory architecture:
- **Working Memory** -- temporary buffer with automatic expiry
- **Episodic Memory** -- events with temporal context, emotional valence
- **Semantic Memory** -- facts with confidence scores, contradiction management
- **Procedural Memory** -- step-by-step procedures with success tracking
- **Strategic Memory** -- patterns with adaptation history

They use PostgreSQL + pgvector + Apache AGE (graph), with automatic clustering into thematic groups with emotional signatures.

**Why this matters for you:** Hexis proves the cognitive memory layer is a real architectural pattern that other engineers are building independently. Your Memberberry + Pulse/Feel is structurally similar but git-backed instead of Postgres-backed. The emotional valence tracking maps to your three-primary color model.

---

## 7. DualityGraph.reason() → Agent with Branching + Convergence

**Your need:** Split a question into dual poles, explore both in parallel, synthesize into converged understanding.

### Precedent: Haystack Multi-Agent System

**Source:** [Haystack Cookbook - Create a Swarm of Agents](https://haystack.deepset.ai/cookbook)

Shows how to create multiple Agent components that each have different system prompts, tools, and reasoning styles, then coordinate their outputs. One agent can be wrapped as a ComponentTool for another:

```python
research_tool = ComponentTool(
    component=research_agent,
    name="research_specialist",
    description="Researches topics from the knowledge base",
    outputs_to_string={"source": "last_message"}
)

coordinator_agent = Agent(
    chat_generator=OpenAIChatGenerator(model="gpt-4o-mini"),
    tools=[research_tool],
    system_prompt="You are a coordinator that delegates research tasks.",
    exit_conditions=["text"]
)
```

**Your adaptation:** Two agents, each assigned one pole of the duality. A coordinator agent receives both outputs and runs convergence logic. The Agent component supports `state_schema` for passing shared context between iterations.

### Precedent: Haystack SuperComponents

**Source:** [Haystack docs - SuperComponents](https://docs.haystack.deepset.ai/docs/supercomponents)

Wraps an entire pipeline as a single reusable component using the `@super_component` decorator. This lets you encapsulate the full duality-explore-converge pipeline as one component that other pipelines can use.

```python
@super_component
class HybridRetriever:
    def __init__(self, document_store):
        self.pipeline = Pipeline()
        # ... add branch components, joiner, ranker
```

**Your adaptation:** `@super_component class DualityEngine` wraps the full split-explore-converge pipeline. From the outside it's a single component with `run(question) -> converged_answer`.

---

## 8. Signal Protocol → Custom I/O Component

**Your need:** Emoji-based compressed communication protocol (💟♡👑🤖🐕💟💬💟💚✅) that encodes state in minimal tokens.

### Precedent: Haystack ConditionalRouter

**Source:** [Haystack docs](https://docs.haystack.deepset.ai/docs/conditionalrouter)

Routes based on pattern matching against component outputs. Your signal parser would be a custom component that decodes emoji sequences into typed state objects, which then feed into a ConditionalRouter for branching.

**No exact open source precedent for emoji-encoded protocols exists.** This is genuinely novel. The closest analog is protocol buffers or MessagePack for compression, but you're doing semantic compression into human-readable symbols. Own it.

---

## 9. Pipeline Serialization → YAML Inspection Layer

**Your need:** Full transparency into every pipeline decision. No black boxes.

### Precedent: Haystack's native serialization

**Source:** [Haystack docs - Pipelines](https://docs.haystack.deepset.ai/docs/pipelines)

Every Haystack pipeline serializes to YAML. Every component's `to_dict()`/`from_dict()` is inspectable. You can save, edit, version, diff, and reload pipelines. Combined with tracing (Langfuse, Arize Phoenix, or LoggingTracer), every component execution is logged with inputs and outputs.

```yaml
# pipeline.yaml - fully inspectable
components:
  behavioral_retriever:
    type: keanu.BehavioralRetriever
    init_parameters:
      dimensions: 20
      scoring_method: "explainable"
  feel_diagnostic:
    type: keanu.FeelWrapper
    init_parameters:
      spectrum: ["ALIVE", "GREY", "BLACK"]
connections:
  - sender: behavioral_retriever.documents
    receiver: feel_diagnostic.documents
```

This is exactly the transparency layer you need. Pipeline state at every point is a YAML diff away.

---

## Summary: What Already Exists vs. What's Novel

| Keanu Component | Pattern Exists? | Best Precedent | Your Differentiation |
|---|---|---|---|
| BehavioralStore | Yes | HyDE, Qdrant-Haystack | Hand-crafted 20-dim vectors, no ML |
| COEFEncoder/Decoder | Yes | OutputAdapter, Outlines component | Content-addressable codec, not format conversion |
| helix_scan (3-branch) | Yes | Hybrid Retrieval tutorial | Three-primary color model as retrieval dimensions |
| Feel wrapper | Yes | LLMMessagesRouter, Guardrails | ALIVE-GREY-BLACK spectrum, not safe/unsafe binary |
| ContentDNS | Yes | DVC, dennwc/cas | Applied to behavioral observations, not ML artifacts |
| Memberberry | Partial | Hexis/AGI-Memory, DVC | Git-backed (not Postgres), conversation-native |
| DualityGraph | Partial | Multi-Agent, SuperComponents | Philosophical convergence, not just task delegation |
| Signal Protocol | No | Nothing close | Genuinely novel semantic compression |
| YAML transparency | Yes | Haystack native | Applied to alignment inspection, not just debugging |

The pattern is clear: the infrastructure patterns all exist and are battle-tested. What's novel is the combination and the purpose: explainable behavioral vectors + cognitive state monitoring + philosophical convergence, all in service of alignment transparency.

You're not reinventing the wheel. You're putting known wheels on a vehicle nobody's built before.