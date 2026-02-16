"""explore: search ingested documents and the web for relevant context.

the library. feed it files, ask it questions, get grounded answers.
uses haystack converters for file processing, chromadb for storage,
keanu's own wellspring for retrieval.

in the world: the explore ability opens the library.
everything you've ingested becomes available to the oracle.
"""

from keanu.abilities import Ability, ability
from keanu.log import info


@ability
class ExploreAbility(Ability):

    name = "explore"
    description = "Search ingested documents and the web for relevant context"
    keywords = [
        "search", "find", "look up", "what does", "rag",
        "explore", "research", "context", "document",
        "ingest", "index", "retrieve",
    ]
    cast_line = "explore opens the library..."

    def can_handle(self, prompt, context=None):
        p = prompt.lower()

        # ingest signals
        if any(phrase in p for phrase in ["ingest", "index this", "add to library"]):
            return True, 0.85

        # retrieval signals
        if any(phrase in p for phrase in [
            "search for", "look up", "find information",
            "what does", "retrieve", "rag",
        ]):
            return True, 0.7

        return False, 0.0

    def execute(self, prompt, context=None):
        p = prompt.lower()

        # ingest mode
        if context and context.get("ingest"):
            return self._do_ingest(context)

        if any(phrase in p for phrase in ["ingest", "index this", "add to library"]):
            path = context.get("file_path", ".") if context else "."
            return self._do_ingest({"file_path": path})

        # retrieval mode (default)
        return self._do_retrieve(prompt, context)

    def _do_ingest(self, context):
        from keanu.abilities.seeing.explore.ingest import ingest

        path = context.get("file_path", ".")
        collection = context.get("collection", "keanu_rag")

        result = ingest(path, collection)
        return {
            "success": result["files"] > 0,
            "result": f"Ingested {result['files']} files ({result['chunks']} chunks) into {result['collection']}",
            "data": result,
        }

    def _do_retrieve(self, prompt, context=None):
        from keanu.abilities.seeing.explore.retrieve import build_context

        include_web = False
        if context:
            include_web = context.get("include_web", False)

        result = build_context(prompt, include_web=include_web)

        if not result:
            return {
                "success": False,
                "result": "No relevant documents found. Try ingesting files first: keanu ingest <path>",
                "data": {},
            }

        return {
            "success": True,
            "result": result,
            "data": {"context_length": len(result)},
        }
