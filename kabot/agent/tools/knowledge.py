from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.tools.base import Tool


class KnowledgeLearnTool(Tool):
    """Tool to permanently learn/ingest a document into the agent's long-term memory."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "knowledge_learn"

    @property
    def description(self) -> str:
        return (
            "Permanently learn and memorize a document from a local file path. "
            "Use this when a user sends a document via chat or points to a local file "
            "that they want you to remember forever. Supports .pdf, .md, .txt, .csv."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the local file to be learned."
                },
                "description": {
                    "type": "string",
                    "description": "A brief summary of what this document is about."
                }
            },
            "required": ["file_path"]
        }

    async def execute(self, file_path: str, description: str = "", **kwargs) -> str:
        from kabot.memory import HybridMemoryManager
        from kabot.utils.document_parser import DocumentParser

        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found at {file_path}"

        logger.info(f"KnowledgeLearnTool: Learning from {path.name}...")
        try:
            text = DocumentParser.extract_text(path)
            # Use chunks for embedding
            chunks = DocumentParser.chunk_text(text, chunk_size=1500, overlap=300)
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return f"Error: Failed to extract text - {str(e)}"

        if not chunks:
            return "Error: No readable text found in the document."

        try:
            # Get the memory manager for the current workspace
            # In AgentLoop, self.workspace is already the session or base workspace path
            # We need to target the knowledge store in Chroma
            chroma_dir = self.workspace / "chroma"
            memory_manager = HybridMemoryManager(persist_directory=str(chroma_dir))

            for i, chunk in enumerate(chunks):
                doc_metadata = {
                    "source": path.name,
                    "description": description,
                    "type": "knowledge_injection",
                    "part": i + 1
                }
                # We inject as a system message/knowledge fact
                content = f"Fact from {path.name}: {chunk}"
                if description:
                    content = f"[{description}] {content}"

                memory_manager.add_messages([
                    {"role": "system", "content": content}
                ], metadata=doc_metadata)

            return f"Success! I have learned {len(chunks)} knowledge chunks from '{path.name}'. I will now remember this information in future conversations."
        except Exception as e:
            logger.error(f"Failed to inject knowledge into memory: {e}")
            return f"Error: Failed to save to long-term memory - {str(e)}"
