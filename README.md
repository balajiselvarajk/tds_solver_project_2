# Project 1 - LLM-Based Assignment Answering API

## Overview
This project is an API that automatically answers questions from graded assignments for the Tools in Data Science course at IIT Madras. The API accepts questions and optional file attachments, processes them, and returns the appropriate answers in a structured format.

## API Endpoint
The API is accessible at the following endpoint:

```
POST https://your-app.vercel.app/api/
```

## Request Format
The API accepts a POST request with the following parameters:

- **question**: A string containing the question related to the graded assignments.
- **file**: An optional file attachment in multipart/form-data format.

### Example Request
You can make a request to the API using `curl` as shown below:

```bash
curl -X POST "https://your-app.vercel.app/api/" \
  -H "Content-Type: multipart/form-data" \
  -F "question=Download and unzip file abcd.zip which has a single extract.csv file inside. What is the value in the 'answer' column of the CSV file?" \
  -F "file=@abcd.zip"
```

## Response Format
The API responds with a JSON object containing the answer. The response will have the following structure:

```json
{
  "answer": "1234567890"
}
```

## Deployment
The application is deployed on Vercel and can be accessed publicly. Ensure that the endpoint is reachable for anyone who needs to use it.

## Usage
1. Prepare your question related to any of the graded assignments (1 to 5).
2. If necessary, attach any relevant files.
3. Send a POST request to the API endpoint with the required parameters.
4. Receive the answer in the JSON format.

## Notes
- Ensure that the files you attach are in the correct format and contain the necessary data for the API to process.
- The API is designed to handle questions related to the following graded assignments:
  - Graded Assignment 1
  - Graded Assignment 2
  - Graded Assignment 3
  - Graded Assignment 4
  - Graded Assignment 5