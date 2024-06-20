import os
import reflex as rx
from openai import AsyncOpenAI
import settings
from database.sqlalchemy import sqlite_db
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Checking if the API key is set properly
if not os.getenv("OPENAI_API_KEY"):
    raise Exception("Please set OPENAI_API_KEY environment variable.")

class QA(rx.Base):
    """A question and answer pair."""
    question: str
    answer: str

DEFAULT_CHATS = {"Intros": []}

class State(rx.State):
    """The app state."""
    question: str
    gpt_response: str
    sql_result: str
    final_answer: str
    chats: dict[str, list[QA]] = DEFAULT_CHATS
    current_chat = "Intros"
    question: str
    processing: bool = False
    new_chat_name: str = ""

    async def init_db(self):
        self.db = sqlite_db()

    def create_chat(self):
        """Create a new chat."""
        self.current_chat = self.new_chat_name
        self.chats[self.new_chat_name] = []

    def delete_chat(self):
        """Delete the current chat."""
        del self.chats[self.current_chat]
        if len(self.chats) == 0:
            self.chats = DEFAULT_CHATS
        self.current_chat = list(self.chats.keys())[0]

    def set_chat(self, chat_name: str):
        """Set the name of the current chat."""
        self.current_chat = chat_name

    @rx.var
    def chat_titles(self) -> list[str]:
        """Get the list of chat titles."""
        return list(self.chats.keys())

    async def process_question(self, form_data: dict[str, str]):
        # Get the question from the form
        logger.debug("Processing question: %s", form_data["question"])
        question = form_data["question"]
        if question == "":
            return

        async for value in self.handle_question(question):
            yield value

    def extract_sql_query(self, response: str) -> str:
        # Logic to extract SQL query from the GPT response
        start = response.find("SQLQuery") + len("SQLQuery") + 2
        if start == -1:
            return None
        
        end = len(response)
        end_sql_result = response.find("SQLResult") 
        if end_sql_result != -1:
            end = end_sql_result
        
        return response[start:end].strip()

    def execute_sql_query(self, query: str) -> list:
        # Execute the SQL query using the sqlite_db class and return the result
        db = sqlite_db()
        return db.execute(query)

    async def generate_detailed_answer(self, query: str, result: list) -> str:
        # Send the SQL result back to GPT to generate the final answer
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        session = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": settings.PROMPT},
                {"role": "user", "content": f"Question: {self.question}\nSQLQuery: {query}\nSQLResult: {result}\nAnswer:"}
            ],
            stream=True,
        )
        detailed_answer_parts = []
        async for item in session:
                content = item.choices[0].delta.content
                if content:  # Check if content is not None
                    detailed_answer_parts.append(content)
        #detailed_answer_parts = [item["choices"][0]["text"] for item in session]
        return "".join(detailed_answer_parts)

    async def handle_question(self, question: str):
        # Add the question to the list of questions
        logger.debug("Handling question: %s", question)
        qa = QA(question=question, answer="")
        if self.current_chat not in self.chats:
            self.chats[self.current_chat] = []
        self.chats[self.current_chat].append(qa)

        # Clear the input and start the processing
        self.processing = True
        yield

        # Build the messages
        messages = [{"role": "system", "content": settings.PROMPT}]
        for qa in self.chats[self.current_chat]:
            messages.append({"role": "user", "content": qa.question})
            messages.append({"role": "assistant", "content": qa.answer})

        messages = messages[:-1]

        try:
            # Start a new session to answer the question
            client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
            session = await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                messages=messages,
                stream=True,
            )

            gpt_response_parts = []
            async for item in session:
                content = item.choices[0].delta.content
                if content:  # Check if content is not None
                    gpt_response_parts.append(content)
            self.gpt_response = "".join(gpt_response_parts)
            logger.debug("GPT response: %s", self.gpt_response)
            
            sql_query = self.extract_sql_query(self.gpt_response)
            logger.debug("Extracted SQL query: %s", sql_query)
            if sql_query:
                sql_result = self.execute_sql_query(sql_query)
                logger.debug("sql_result: %s", self.sql_result)
                self.sql_result = str(sql_result)
                detailed_answer = await self.generate_detailed_answer(sql_query, sql_result)
                self.final_answer = detailed_answer
                logger.debug("Final answer: %s", self.final_answer)

                # Update the last QA with the final answer
                self.chats[self.current_chat][-1].answer = self.final_answer
                self.processing = False

                #yield self.final_answer
                yield rx.Events.Update(self)
            else:
                logger.debug("No SQL query extracted from GPT response")
        
        except Exception as e:
            logger.error("Error handling question: %s", e)
        
        logger.debug("Finished handling question")
