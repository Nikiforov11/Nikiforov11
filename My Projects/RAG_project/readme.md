# PDF Question Answering with RAG

This project is a local Retrieval-Augmented Generation (RAG) application. It
lets a user upload PDF documents, indexes their contents as embeddings, and
answers questions using only the most relevant passages retrieved from those
documents.

The project is built as an event-driven pipeline. **Streamlit** provides the
interface, **Inngest** runs the ingestion and query functions, **Qdrant** stores
the vectors, and the **Google Gemini API** provides both embeddings and the
answering model through its OpenAI-compatible API.

## How it works

```text
PDF upload
		|
		v
Streamlit saves the file in uploads/
		|
		v
Inngest event: rag/ingest_pdf
		|
		+--> LlamaIndex PDFReader extracts text
		+--> SentenceSplitter creates overlapping chunks
		+--> Gemini Embeddings API creates 3,072-dimensional vectors
		+--> Qdrant stores vectors and source text

Question
		|
		v
Inngest event: rag/query_pdf_ai
		|
		+--> Gemini embeds the question
		+--> Qdrant retrieves the most relevant chunks
		+--> Gemini generates an answer from the retrieved context
		v
Answer and source filenames in the Streamlit UI
```

The answer function is instructed to use only the retrieved context. The
retrieved source filenames are also returned with each answer so the result can
be traced back to the uploaded documents.

## Project structure

| File or folder | Purpose |
|---|---|
| `streamlip_app.py` | Streamlit interface for uploading PDFs and asking questions |
| `main.py` | FastAPI and Inngest function definitions |
| `data_loader.py` | PDF extraction, text chunking, and Gemini embeddings |
| `vector_db.py` | Qdrant collection setup, vector upserts, and similarity search |
| `custom_types.py` | Pydantic models used by the ingestion and query workflows |
| `requirements.txt` | Python dependencies |
| `uploads/` | Local copies of uploaded PDFs |
| `qdrant_storage/` | Local Qdrant storage directory when using a local Qdrant instance |

## Requirements

- Python 3.10 or newer
- A Gemini API key
- A running Qdrant instance at `http://localhost:6333`
- The Inngest CLI for the local event server

The application expects the following services to be available:

| Service | Default address | Used for |
|---|---|---|
| Qdrant | `http://localhost:6333` | Vector storage and similarity search |
| Inngest | `http://127.0.0.1:8288` | Local event execution and run polling |

## Setup

From the repository root, create or activate the project's virtual environment
and install its dependencies:

```powershell
cd "My Projects/RAG_project"
pip install -r requirements.txt
```

Create a `.env` file in this folder and add your Gemini credentials:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
_MODEL=your_gemini_model_name
```
## Running the application

Start Qdrant first. For this project I used Docker for the qdrant instance, So first we need to run it as in a Docker container:

```powershell
docker run --name rag-qdrant -p 6333:6333 qdrant/qdrant
```

In a second terminal, start the FastAPI application so Inngest can discover the
registered functions:

```powershell
cd "My Projects/RAG_project"
uvicorn main:app --reload
```

In a third terminal, start the local Inngest development server and point it at
the FastAPI endpoint. The exact command depends on the installed Inngest CLI;
the development server should use the FastAPI endpoint
`http://127.0.0.1:8000/api/inngest`.

Finally, in a fourth terminal, start Streamlit:

```powershell
cd "My Projects/RAG_project"
streamlit run streamlip_app.py
```

Open the local URL printed by Streamlit. Upload a PDF, wait for ingestion to
complete, then enter a question and choose how many chunks to retrieve.

The number of retrieved chunks can be set from 1 to 20 in the UI. The default
is 5. The Streamlit app polls the local Inngest API until the query function
has finished and then displays the answer and its source filenames.

## Main workflow

### Ingest a PDF

1. Select a PDF in the Streamlit interface.
2. The file is saved under `uploads/`.
3. Inngest triggers `rag/ingest_pdf`.
4. `PDFReader` extracts the document text.
5. `SentenceSplitter` creates chunks of 1,000 tokens with 200-token overlap.
6. Gemini creates an embedding for each chunk.
7. Qdrant stores each vector together with its text and source filename.

Chunk IDs are deterministic UUIDs based on the source ID and chunk index, so
re-ingesting the same source updates the same points instead of creating random
IDs each time.

### Ask a question

1. Enter a question and select `top_k`, the number of chunks to retrieve.
2. Inngest triggers `rag/query_pdf_ai`.
3. Gemini embeds the question.
4. Qdrant performs cosine-similarity search in the `docs` collection.
5. The retrieved chunks are sent to Gemini as context.
6. The generated answer and source filenames are returned to Streamlit.

## Limitations

- The application currently uses one Qdrant collection named `docs` for all
	uploaded PDFs.
- Uploaded files are stored locally in `uploads/`; there is no authentication,
	file management UI, or cloud object storage.
- Answer quality depends on PDF text extraction, chunking, embedding quality,
	and the selected Gemini model.
- Scanned PDFs without an embedded text layer may need OCR before ingestion.
- The default Qdrant connection is hard-coded to `http://localhost:6333` in
	`vector_db.py`.
- This is a local portfolio project rather than a production deployment. API
	keys, access control, retries, and operational monitoring should be added
	before exposing it to other users.

## Tech stack

- Python
- Streamlit
- FastAPI
- Inngest
- LlamaIndex PDFReader and SentenceSplitter
- Google Gemini Embeddings and generative models
- OpenAI Python client with Gemini's OpenAI-compatible endpoint
- Qdrant
- Pydantic
