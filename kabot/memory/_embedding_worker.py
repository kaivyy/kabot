"""Standalone subprocess worker for embedding generation.

This file is invoked as a separate Python process:
    python -m kabot.memory._embedding_worker <model_name>

Communication protocol (stdin/stdout, JSON lines):
    Request:  {"id": "req_1", "type": "embed", "data": "hello world"}
    Response: {"id": "req_1", "status": "ok", "result": [0.1, 0.2, ...]}
"""

import json
import sys


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "all-MiniLM-L6-v2"

    # Import and load model
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)

    # Signal ready
    sys.stdout.write(json.dumps({"id": "init", "status": "ok", "result": True}) + "\n")
    sys.stdout.flush()

    # Process requests from stdin
    # Use readline() in while loop instead of 'for line in sys.stdin'
    # because the latter has buffering issues with subprocess pipes on Windows
    while True:
        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                break

            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        except EOFError:
            break

        req_id = request.get("id", "unknown")
        req_type = request.get("type", "")
        data = request.get("data")

        try:
            if req_type == "embed":
                embedding = model.encode(data)
                if hasattr(embedding, "tolist"):
                    embedding = embedding.tolist()
                response = {"id": req_id, "status": "ok", "result": embedding}

            elif req_type == "embed_batch":
                embeddings = model.encode(data)
                if hasattr(embeddings, "tolist"):
                    embeddings = embeddings.tolist()
                response = {"id": req_id, "status": "ok", "result": embeddings}

            elif req_type == "ping":
                response = {"id": req_id, "status": "ok", "result": True}

            elif req_type == "shutdown":
                sys.stdout.write(json.dumps({"id": req_id, "status": "ok", "result": "bye"}) + "\n")
                sys.stdout.flush()
                break

            else:
                response = {"id": req_id, "status": "error", "result": f"Unknown type: {req_type}"}

        except Exception as e:
            response = {"id": req_id, "status": "error", "result": str(e)}

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
