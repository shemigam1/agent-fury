import os
from dotenv import load_dotenv
from google import genai
import sys
from google.genai import types
from call_function import available_functions
from prompts import system_prompt
from call_function import call_function

messages = []

def main():
    load_dotenv()

    verbose = "--verbose" in sys.argv
    args = []
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            args.append(arg)

    if not args:
        print("AI Code Assistant")
        print('\nUsage: python main.py "your prompt here" [--verbose]')
        print('Example: python main.py "How do I build a calculator app?"')
        sys.exit(1)

    user_prompt = " ".join(args)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    if verbose:
        print(f"User prompt: {user_prompt}\n")
    messages.append(types.Content(role="user", parts=[types.Part(text=user_prompt)]),)

    generate_content(client, messages, verbose)


def generate_content(client, messages, verbose):

    max_iters = 20
    for i in range(max_iters):
        response = client.models.generate_content(
            model='gemini-2.0-flash-001', 
            contents=messages,
            config=types.GenerateContentConfig(
            tools=[available_functions], system_instruction=system_prompt
            ),
        )
        if response is None or response.usage_metadata is None:
            print("response in malformed")
            return
        if verbose:
            print("Prompt tokens:", response.usage_metadata.prompt_token_count)
            print("Response tokens:", response.usage_metadata.candidates_token_count)

        if not response.candidates or not response.function_calls:
            return response.text

        function_responses = []

        for candidate in response.candidates:
            if candidate is None or candidate.content is None:
                continue
            messages.append(candidate.content)


        for function_call_part in response.function_calls:
            function_call_result = call_function(function_call_part, verbose)
            messages.append(function_call_result)

        # if not function_responses:
        #     raise Exception("no function responses generated, exiting.")



        print("Response:")
        print(response.text)


if __name__ == "__main__":
    main()
