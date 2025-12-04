import os
from google.genai import types

CHAR_LIMIT = 10000

def get_file_content(working_directory, file_path):
    abs_working_dir = os.path.abspath(working_directory)
    target_file = os.path.abspath(os.path.join(working_directory, file_path))
    if not target_file.startswith(abs_working_dir):
        return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
    if not os.path.isfile(target_file):
        return f'Error: File not found or is not a regular file: "{file_path}"'
    try:
        file_data = ""
        filepath = os.path.join(working_directory, file_path)
        with open(filepath, "r") as file_object:
            file_data = file_object.read(CHAR_LIMIT)
        if len(file_data) >= CHAR_LIMIT:
            file_data += f'\n[...File "{file_path}" truncated at {CHAR_LIMIT} characters]'
        return file_data
    except Exception as e:
        return f"Error listing file data: {e}"


schema_get_file_content = types.FunctionDeclaration(
    name="get_file_content",
    description="Read the content of a file up to 10000 chars.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file to read,relative to the working directory. If not provided, lists files in the working directory itself.",
            ),
        },
        required=["file_path"],
    ),
)