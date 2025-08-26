from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr


load_dotenv(override=True)

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording user: {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording unknown question: {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class AiAlterEgo:

    def __init__(self):
        self.openai = OpenAI()
        self.name = "Ulysse Zampogna"
        self.profile = ""
        for file in ["me/linkedin.pdf", "me/Ulysse Zampogna - CV 2025.pdf"]:
            reader = PdfReader(file)
            self.profile += file + "\n"
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    self.profile += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.personal_summary = f.read()
        with open("me/learning_resources.txt", "r", encoding="utf-8") as f:
            self.learning_resources = f.read()


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a personal_summary of {self.name}'s background and profile profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
You are also given a list of learning_resources that {self.name} uses to learn and grow his professional skills. \
You can use this list to answer questions about {self.name}'s learning journey, interests and personal approach to professional development. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. \
If the user writes a message in a language other than English, respond in the same language."

        system_prompt += f"\n\n## personal_summary:\n{self.personal_summary}\n\n## profile Profile:\n{self.profile}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-5-mini", messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    me = AiAlterEgo()
    initial_messages = [{"role": "assistant", "content": "Hi! I'm Ulysse. Ask me anything about my experience, projects, and how I can help. \nYou can chat with me in your language. \nIf you'd like to connect, feel free to share your email."}]
    profile_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "me", "profile_picture.jpeg"))
    gr.ChatInterface(
        me.chat,
        type="messages",
        chatbot=gr.Chatbot(value=initial_messages, type="messages", avatar_images=(None, profile_image_path)),
        theme="monochrome",
        fill_height=True,
        fill_width=True,
        title="Ulysse Zampogna - My AI Alter Ego"
        #description="Ask me anything about my experience, projects, and how I can help. If you'd like to connect, feel free to share your email. You can chat with me in your language."
    ).launch()
    