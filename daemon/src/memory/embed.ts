// daemon/src/memory/embed.ts
// Embeddings for semantic memory search.
//
// Uses @huggingface/transformers (ONNX in-process, no Python needed).
// Model: all-MiniLM-L6-v2 (384 dimensions).
// Lazy-loaded on first call. Cached after that.

let embedder: Awaited<ReturnType<typeof loadPipeline>> | null = null
let loading: Promise<typeof embedder> | null = null

async function loadPipeline() {
	const { pipeline, env } = await import("@huggingface/transformers")
	// Cache models in ~/.keanu/models/ instead of node_modules
	env.cacheDir = `${process.env.HOME || "~"}/.keanu/models`
	return pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2")
}

async function getEmbedder() {
	if (embedder) return embedder
	if (loading) return loading
	loading = loadPipeline()
	embedder = await loading
	loading = null
	return embedder
}

/**
 * Embed a single text string into a 384-dim vector.
 * First call downloads the model (~23MB). Subsequent calls are fast.
 */
export async function embed(text: string): Promise<number[]> {
	const pipe = await getEmbedder()
	const output = await pipe(text, { pooling: "mean", normalize: true })
	// output.tolist() returns number[][] for batch, we want the first
	const vectors = output.tolist() as number[][]
	return vectors[0]
}

/**
 * Embed multiple texts in a batch.
 */
export async function embedBatch(texts: string[]): Promise<number[][]> {
	if (texts.length === 0) return []
	const pipe = await getEmbedder()
	const output = await pipe(texts, { pooling: "mean", normalize: true })
	return output.tolist() as number[][]
}

/** Embedding dimensions for all-MiniLM-L6-v2 */
export const EMBEDDING_DIM = 384
