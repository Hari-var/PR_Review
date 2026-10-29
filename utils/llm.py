from openai import AzureOpenAI #type: ignore
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# import google.generativeai as genai #type: ignore
import time
from .config import Content_generator_model_config as cgconfig

def get_azure_response(text):
    endpoint = None
    deployment = None
    subscription_key = None
    api_version = None
    try:
        endpoint = cgconfig.AI_content_endpoint
        deployment = cgconfig.AI_content_model
        subscription_key = cgconfig.AI_content_key
        api_version = cgconfig.AI_content_version
        print("=+="*30)
        print(endpoint, deployment, subscription_key, api_version)

        if not subscription_key:
            return "Error: AZURE_OPENAI_KEY not found in environment variables"
 
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=subscription_key,
        )
 
        response = client.responses.create(
            model=deployment,
            instructions="You are a helpful assistant.",
            input=text,
        )

        return response.output[0].content[0].text #.output.contents[0].text if response.output and response.output.contents else "No content in response"
    except Exception as e:
        return {"Azure Error": str(e)}

if __name__ == "__main__":
    print(get_azure_response("Hello, how are you?"))