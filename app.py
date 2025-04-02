import zipfile
import os
import tempfile
import aiofiles
import asyncio
from werkzeug.utils import secure_filename
import pandas as pd
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import subprocess
import hashlib
import shutil
import requests

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configuration
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'zip', 'md'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 10MB
LLM_FOUNDRY_TOKEN = os.getenv('LLM_FOUNDRY_TOKEN')

""" Path: /gemini/v1beta/models/gemini-2.0-flash-001:generateContent
gemini: This likely refers to the specific project or suite of models offered by LLM Foundry.
v1beta: This indicates that the API is in the beta version of its first iteration. It may still be undergoing testing and could change in the future.
models/gemini-2.0-flash-001: This specifies the particular model you are accessing. In this case, "gemini-2.0-flash-001" is the model identifier.
:generateContent: This part of the endpoint suggests that the action being performed is to generate content using the specified model.
 """
LLM_ENDPOINT = "https://llmfoundry.straive.com/gemini/v1beta/models/gemini-2.0-flash-001:generateContent"

def is_file_allowed(filename: str) -> bool:
    """Check if the file extension is allowed."""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

async def identify_file_type(file_path: str) -> str:
    """Determine file type based on extension and content."""
    extension = os.path.splitext(file_path)[1].lower()
    
    # Mapping of extensions to file types
    extension_map = {
        '.zip': 'zip',
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.md': 'md'
    }
    
    # Check if the extension is in the mapping
    if extension in extension_map:
        return extension_map[extension]
    
    # Try to read the file content if the extension is unknown
    try:
        # Attempt to read as CSV first
        pd.read_csv(file_path, nrows=1)
        return 'csv'
    except pd.errors.EmptyDataError:
        # Handle empty CSV files gracefully
        pass
    except Exception:
        # If reading as CSV fails, try reading as Excel
        try:
            pd.read_excel(file_path, nrows=1)
            return 'excel'
        except Exception:
            pass
    
    return 'unknown'

async def collect_file_data(file_path: str) -> str:
    """Extract information from different file types."""
    file_type = await identify_file_type(file_path)

    # Mapping of file types to their processing functions
    processing_functions = {
        'zip': handle_zip_file,
        'csv': handle_csv_file,
        'excel': handle_excel_file,
        'md': handleMarkdownFile
    }

    # Get the processing function based on the file type
    process_function = processing_functions.get(file_type)

    if process_function:
        return await process_function(file_path)
    else:
        return "Unsupported file type"

async def handle_zip_file(zip_path: str) -> str:
    """Process ZIP file and return information about its contents."""
    info = []
    
    try:
        async with aiofiles.open(zip_path, 'rb') as zip_file:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                # Iterate through the files in the ZIP archive
                for file in zip_ref.namelist():
                    if file.endswith('/'):
                        continue  # Skip directories
                    
                    # Read the file content directly into memory
                    with zip_ref.open(file) as f:
                        file_content = await f.read()
                        
                        # Create a temporary file path
                        temp_path = os.path.join(tempfile.gettempdir(), secure_filename(file))
                        
                        # Write the content to a temporary file asynchronously
                        async with aiofiles.open(temp_path, 'wb') as temp_file:
                            await temp_file.write(file_content)
                        
                        # Collect data from the temporary file
                        file_info = await collect_file_data(temp_path)
                        info.append(f"File '{file}' in ZIP contains:\n{file_info}")
                        
                        # Clean up the temporary file
                        os.remove(temp_path)
    except Exception as e:
        return f"Error processing ZIP file: {str(e)}"
    
    return "\n".join(info)

async def handle_csv_file(csv_path: str, num_preview_rows: int = 5) -> str:
    """Process CSV file and return summary information."""
    try:
        df = pd.read_csv(csv_path)
        
        # Store the number of rows and columns
        num_rows, num_columns = df.shape
        
        # Create a summary string
        summary = (
            f"CSV file with {num_rows} rows and {num_columns} columns.\n"
            f"Columns: {', '.join(df.columns)}.\n"
            f"First {num_preview_rows} rows:\n{df.head(num_preview_rows).to_string(index=False)}"
        )
        return summary
    except FileNotFoundError:
        return f"Error: The file '{csv_path}' was not found."
    except pd.errors.EmptyDataError:
        return "Error: The file is empty."
    except pd.errors.ParserError:
        return "Error: There was a problem parsing the file."
    except Exception as e:
        return f"Error processing CSV: {str(e)}"

async def handle_excel_file(excel_path: str) -> str:
    """Process Excel file and return summary information."""
    try:
        # Read all sheets into a dictionary of DataFrames
        sheets_dict = pd.read_excel(excel_path, sheet_name=None)
        
        # Create summary information for each sheet using list comprehension
        info = [
            f"Sheet '{sheet_name}' has {len(df)} rows and {len(df.columns)} columns. "
            f"Columns: {', '.join(df.columns)}. First few rows:\n{df.head().to_string()}"
            for sheet_name, df in sheets_dict.items()
        ]
        
        return "\n\n".join(info)
    
    except FileNotFoundError:
        return f"Error: The file '{excel_path}' was not found."
    except pd.errors.EmptyDataError:
        return "Error: The Excel file is empty."
    except Exception as e:
        return f"Error processing Excel file: {str(e)}"

async def handleMarkdownFile(md_path: str) -> str:
    """Process Markdown file and return its content."""
    try:
        async with aiofiles.open(md_path, 'r') as f:
            content = await f.read()
        return f"Markdown file content:\n{content}"
    except FileNotFoundError:
        return "Error: The specified Markdown file was not found."
    except IOError as e:
        return f"Error reading Markdown file: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

async def run_command(command: str, cwd: str = None) -> str:
    """Execute a shell command asynchronously and return its output."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return f"Error: Command failed with exit code {process.returncode}. Output: {stderr.decode().strip()}"

        return stdout.decode().strip()

    except asyncio.TimeoutError:
        return "Error: Command execution timed out."
    except Exception as e:
        return f"Error executing command: {str(e)}"

async def compute_sha256(file_path: str) -> str:
    """Calculate the SHA256 hash of a file in an optimized way by reading it in chunks."""
    sha256_hash = hashlib.sha256()  # Create a new SHA256 hash object
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(8192)  # Read the file in 8 KB chunks
                if not chunk:  # If the chunk is empty, we reached the end of the file
                    break
                sha256_hash.update(chunk)  # Update the hash with the chunk
        return sha256_hash.hexdigest()  # Return the hexadecimal digest of the hash
    except Exception as e:
        return f"Error calculating SHA256: {str(e)}"

async def generate_response(question: str, file_info: str = None) -> str:
    """Generate response using Gemini 2.0 Flash model."""
    
    # Define the system prompt once
    system_prompt = (
        "You are an expert Data Science teaching assistant for an online Degree in Data Science program. "
        "Your task is to provide precise answers to graded assignment questions, ensuring they match exactly what is expected.\n\n"
        "Key guidelines:\n"
        "1. Provide exact answers without additional text or explanations.\n"
        "2. For numerical answers, give the exact number.\n"
        "3. For file-based questions, analyze the provided file information and perform necessary calculations or commands, providing the result.\n"
        "4. For command outputs, provide the exact output as it would appear, not a description or example. If execution is not possible, give a realistic lookalike output.\n"
        "5. For Google Sheets formulas, calculate the result and provide the numerical answer.\n"
        "6. For multi-step questions, break down the steps and provide the final answer."
    )
    # Construct the message prompt based on the presence of file_info
    attached_file_info = f'Attached file information:\n{file_info}\n' if file_info else ''
    message_prompt = (
        f"Assignment question: {question}\n\n"
        f"{attached_file_info}"
        "Please provide the exact answer to be entered in the assignment."
    )
    
    # Prepare the request payload
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": message_prompt}]}],
        "generationConfig": {"temperature": 0},
        "tools": [{"google_search": {}}]
    }
    
    try:
        # Make the API request
        response = requests.post(
            LLM_ENDPOINT,
            headers={
                "Content-Type": "application/json", 
                "Authorization": f"Bearer {LLM_FOUNDRY_TOKEN}:project-2"
            },
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        # Extract the answer from the response
        candidates = response.json().get('candidates', [])
        if candidates:
            return candidates[0]['content']['parts'][0]['text'].strip()
        
        return "Error: Could not extract answer from model response"
    
    except requests.exceptions.RequestException as e:
        return f"Error calling LLM API: {str(e)}"

@app.post("/api/")
async def answer_question(question: str = Form(...), file: UploadFile = None):
    """API endpoint to answer questions with optional file attachments."""
    answer = None
    file_info = None

    if file:
        if not await is_file_allowed(file.filename):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Create a temporary directory and file path
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, secure_filename(file.filename))

        try:
            # Save the file temporarily
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # Check file size
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail="File too large")

            # Process the file
            file_type = await identify_file_type(file_path)
            file_info = await collect_file_data(file_path)

            # Handle specific questions that require local execution
            if "sha256sum" in question.lower() and file_type == 'md':
                answer = await compute_sha256(file_path)
            elif "prettier" in question.lower() and "sha256sum" in question.lower() and file_type == 'md':
                prettier_command = f"npx -y prettier@3.4.2 {file_path} | sha256sum"
                answer = await run_command(prettier_command, cwd=temp_dir)
            elif "code -s" in question.lower():
                answer = await run_command("code -s")

        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    if answer is None:
        answer = await generate_response(question, file_info)

    return JSONResponse(content={"answer": answer})