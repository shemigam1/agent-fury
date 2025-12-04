🤖 **AI Code Assistant**

This project is a sophisticated Python-based AI agent designed to interact with a local development environment. Leveraging Google Gemini's powerful generative AI capabilities, it provides an intelligent assistant that can autonomously understand, navigate, and modify codebases by interacting with the file system and executing Python scripts. It's a valuable tool for automating development tasks, exploring projects, and debugging.

## Features

-   🧠 **Intelligent Code Interaction**: Utilizes Google Gemini to interpret prompts and execute actions within a coding project.
-   📂 **File System Management**: Capable of listing directory contents, reading file information, and retrieving file content.
-   ✍️ **Code Modification**: Enables writing and overwriting file content, allowing the AI to modify source code or configuration files.
-   🚀 **Python Script Execution**: Executes Python files with specified arguments, capturing and returning their standard output and error streams.
-   🛡️ **Sandboxed Operations**: All file system and execution operations are constrained to a predefined working directory for security and isolation.

## Technologies Used

| Technology              | Description                                        | Version/Platform       |
| :---------------------- | :------------------------------------------------- | :--------------------- |
| Python                  | Primary programming language                       | 3.12                   |
| Google Generative AI    | AI model for intelligent decision-making           | `google-genai==1.12.1` |
| `python-dotenv`         | Environment variable management                    | `python-dotenv==1.1.0` |
| `subprocess` module     | For running external Python scripts                | Standard Library       |
| `os` module             | For file system interactions                       | Standard Library       |
| `unittest`              | For testing the calculator module                  | Standard Library       |

## Getting Started

Follow these steps to set up the AI Code Assistant locally.

### Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/ai-agent.git
    cd ai-agent
    ```

2.  **Set up Python Environment**:
    This project requires Python 3.12. It's recommended to use `pyenv` or `conda` for environment management.
    ```bash
    # Using pyenv
    pyenv install 3.12
    pyenv local 3.12

    # Or ensure you are using Python 3.12
    python3.12 -m venv venv
    source venv/bin/activate # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -e .
    ```

### Environment Variables

Create a `.env` file in the root of the project (`ai-agent/`) and add your Google Gemini API key:

```ini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
```

## Usage

Run the `main.py` script with your prompt. The AI will then utilize its tools to attempt to fulfill your request.

```bash
python main.py "your prompt here"
```

**Example Scenarios**:

1.  **Ask about a project**:
    ```bash
    python main.py "What does the calculator project do and how can I run its tests?"
    ```

2.  **Request a change**:
    ```bash
    python main.py "The calculator module needs to support exponentiation. Add support for the '^' operator to the calculator/pkg/calculator.py file and update the tests."
    ```

3.  **Use verbose output to see AI reasoning**:
    ```bash
    python main.py "List all files in the calculator directory" --verbose
    ```

## AI Tool Function Definitions

The AI Code Assistant interacts with the environment through a set of predefined tool functions. These functions act as an internal API, allowing the AI model to perform operations like file system navigation, content manipulation, and code execution. Each function has a clear schema for parameters, expected responses, and potential errors.

### Tool Functions

#### `get_files_info`
**Description**: Lists files in the specified directory along with their sizes, constrained to the working directory.

**Request**:
```json
{
  "directory": "path/to/directory" // Optional: The directory to list files from, relative to the working directory. Defaults to "."
}
```

**Response**:
```json
{
  "result": "- main.py: file_size=714 bytes, is_dir=False\n- tests.py: file_size=1426 bytes, is_dir=False\n- pkg: file_size=4096 bytes, is_dir=True"
}
```

**Errors**:
-   `Error: Cannot list "[directory]" as it is outside the permitted working directory`
-   `Error: "[directory]" is not a directory`
-   `Error listing files: [detailed error message]`

#### `get_file_content`
**Description**: Reads the content of a file up to 10000 characters.

**Request**:
```json
{
  "file_path": "path/to/file.py" // Required: The file to read, relative to the working directory.
}
```

**Response**:
```json
{
  "result": "import sys\nfrom pkg.calculator import Calculator\nfrom pkg.render import format_json_output\n\ndef main():\n    calculator = Calculator()\n    if len(sys.argv) <= 1:\n        print(\"Calculator App\")\n        # ... truncated output"
}
```

**Errors**:
-   `Error: Cannot read "[file_path]" as it is outside the permitted working directory`
-   `Error: File not found or is not a regular file: "[file_path]"`
-   `Error listing file data: [detailed error message]`

#### `run_python_file`
**Description**: Executes a Python file within the working directory and returns the output from the interpreter.

**Request**:
```json
{
  "file_path": "path/to/script.py", // Required: Path to the Python file to execute, relative to the working directory.
  "args": ["arg1", "arg2"]           // Optional: Arguments to pass to the Python file.
}
```

**Response**:
```json
{
  "result": "STDOUT:\nCalculator App\nUsage: python main.py \"<expression>\"\nSTDERR:\n\nProcess exited with code 1"
}
```

**Errors**:
-   `Error: Cannot execute "[file_path]" as it is outside the permitted working directory`
-   `Error: File "[file_path]" not found.`
-   `Error: "[file_path]" is not a Python file.`
-   `Error: executing Python file: [detailed error message]`

#### `write_file`
**Description**: Writes content to a file, overwriting existing content.

**Request**:
```json
{
  "file_path": "path/to/new_file.txt", // Required: The file to write to, relative to the working directory.
  "content": "New content for the file." // Required: The content to write into the file.
}
```

**Response**:
```json
{
  "result": "Successfully wrote to \"path/to/new_file.txt\" (25 characters written)"
}
```

**Errors**:
-   `Error: Cannot write to "[file_path]" as it is outside the permitted working directory`
-   `Error: File not found or is not a regular file: "[file_path]"`
-   `Error writing file data: [detailed error message]`

## License

No explicit license information provided.

## Author Info

Connect with me:

-   **LinkedIn**: [Your LinkedIn Profile]
-   **Portfolio**: [Your Personal Website/Portfolio]
-   **X (Twitter)**: [@YourTwitterHandle]

---
![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-API-4285F4?logo=google&logoColor=white)

[![Readme was generated by Dokugen](https://img.shields.io/badge/Readme%20was%20generated%20by-Dokugen-brightgreen)](https://www.npmjs.com/package/dokugen)