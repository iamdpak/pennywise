from PIL import Image
import os
import re
import requests
import base64
import json
import psycopg2
from psycopg2 import sql
import faiss
import ollama
import numpy as np
import datetime

MODEL_NAME = "llama3.2-vision"
OLLAMA_URL = "http://localhost:11434/api/generate"

class GroceryDB:
    def __init__(self, dbname, user, password, host='localhost', port='5432'):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.connection = None
        self.create_database()
        self.connect()
        self.create_tables()
        self.grocery_list = []
        self.vectordb = None
        self.init_grocery_vectorDB("/home/deepak/workspace/learn_AI/apps/grocery_list.txt")
        #self.search_grocery_vectorDB("Black Grapes seedless")

    def connect(self):
        """Establishes a connection to the PostgreSQL database."""
        self.connection = psycopg2.connect(
            dbname=self.dbname, user=self.user, password=self.password, host=self.host, port=self.port
        )
        self.connection.autocommit = True

    def create_database(self):
        """Creates the database if it does not already exist."""
        temp_conn = psycopg2.connect(dbname='postgres', user='postgres', password=self.password, host=self.host, port=self.port)
        temp_conn.autocommit = True
        cursor = temp_conn.cursor()
        cursor.execute(sql.SQL("""
            SELECT 1 FROM pg_database WHERE datname = %s
        """), (self.dbname,))
        if not cursor.fetchone():
            cursor.execute(sql.SQL("""
                CREATE DATABASE {}
            """).format(sql.Identifier(self.dbname)))
        cursor.close()
        temp_conn.close()

    def create_tables(self):
        """Creates the required tables if they do not exist."""
        cursor = self.connection.cursor()
        
        # Create grocery_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grocery_items (
                id SERIAL PRIMARY KEY,
                price DECIMAL(10, 2) NOT NULL,
                shop_name TEXT NOT NULL,
                shop_ABN TEXT NOT NULL,
                shop_address TEXT NOT NULL,
                category TEXT NOT NULL,
                date_purchased DATE NOT NULL
            )
        """)
        
        self.connection.commit()
        cursor.close()

    def update_table(self, json_record):     
        cursor = self.connection.cursor()   
        sql_query = """
        INSERT INTO grocery_items (price, shop_name, shop_ABN, shop_address, category, date_purchased)
        VALUES (%s, %s, %s, %s, %s, %s);
        """

        cursor.execute(sql_query, (
            json_record["price"],
            json_record["shop_name"],
            json_record["shop_abn"],
            json_record["shop_address"],
            json_record["item_category"],
            json_record["date_purchased"]
        ))
        
        
        self.connection.commit()
        cursor.close()        
        
    def close(self):
        """Closes the database connection."""
        if self.connection:
            self.connection.close()


    def get_embedding(self, text):
        response = ollama.embeddings(model=MODEL_NAME, prompt=text)
        return np.array(response['embedding'], dtype=np.float32)

    def init_grocery_vectorDB(self, grocery_list_file):
        self.grocery_list = open(grocery_list_file).read().split("\n")
        
        # Generate embeddings for all grocery items
        grocery_embeddings = np.array([self.get_embedding(item) for item in self.grocery_list])

        # Create a FAISS index
        dimension = len(grocery_embeddings[0])
        self.vectordb = faiss.IndexFlatL2(dimension)
        self.vectordb.add(grocery_embeddings)

    # Function to search for the most relevant grocery item
    def search_grocery_vectorDB(self, query, top_k=1):
        query_embedding = np.array([self.get_embedding(query)], dtype=np.float32)
        distances, indices = self.vectordb.search(query_embedding, top_k)
        
        results = [(self.grocery_list[idx], distances[0][i]) for i, idx in enumerate(indices[0])]
        return results
    

class PennyWise:
    def __init__(self):
        # A dictionary to store the image path and extracted text
        self.receipt_data = {}
        self.gdb = GroceryDB(dbname="gdb", user="postgres", password="password", host='localhost', port='5432')
        


    def process_receipts(self, image_path):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"The file {image_path} does not exist.")

        # Use LLM to parse the image data
        self.receipt_data[image_path] = self.llm_passthrough(image_path)

        # update the db
        print (self.receipt_data[image_path])

        for json_record in self.receipt_data[image_path]['grocery_items']:
            self.gdb.update_table(json_record)



    def llm_passthrough(self, image_path):
        
        json_str = json.dumps({"grocery_items":[{
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "item_name": "pink lady apple",
            "price": "5.99",
            "date_purchased": "2025-02-18",
            "shop_name": "woolworths",
            "shop_address": "123 Main St, Springfield, IL",
            "shop_abn": "1234567",
            "item_category": "Pink Lady Apples",
        },
        {
            "uuid": "550e8400-e29b-41d4-a716-446655240100",
            "item_name": "Mango Honey Gold",
            "price": "5.99",
            "date_purchased": "2025-02-18",
            "shop_name": "woolworths",
            "shop_address": "123 Main St, Springfield, IL",
            "shop_abn": "1234567",
            "item_category": "Honey Gold Mangoes",
        }]})
        text_prompt = text_prompt = f"""Given the receipt image extract the grocery items with their cost and other receipt details line date and shop details. 
        Respond to me ONLY in JSON format similar to the example below:
        {json_str}
        Wrap the JSON output within triple backticks.
        Generate uuid using uuid4 generator.
        Do not use $ for the price.
        Give me the date purchased in YYYY-MM-DD format.
        """

        llm_response  = self.send_request(image_path, text_prompt)

        #print (llm_response)
        json_data = None
        json_match = re.search(r"```(?:json)?\n(.*?)\n```", llm_response, re.DOTALL)
        if json_match:
            extracted_json = json_match.group(1)
            json_data = json.loads(extracted_json)  # Convert JSON string to a Python object
            print(json.dumps(json_data, indent=4))

        for i in range(len(json_data["grocery_items"])):
            #item_categories = self.gdb.search_grocery_vectorDB(json_data["grocery_items"][i]["item_name"])
            #tmp_prompt = f"The response should contain only the item category title. do you think {item_categories[0][0]} and {json_data['grocery_items'][i]['item_name']} are the same? If yes, respond with item catetory else suggest me the correct item category. Make sure you respond only the item category and no supporting text" 
            tmp_prompt = f"Given the item name extracted from the receipt, {json_data['grocery_items'][i]['item_name']} what is the item name? Respond only with the item name and NOT as a statement. Choose from the list {self.gdb.grocery_list} if present." 
            response_item_category = self.send_request_textonly(tmp_prompt)
            json_data["grocery_items"][i]["item_category"] = response_item_category
        return json_data



    def encode_image(self, image_path):
        """Encodes an image to base64 format."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def send_request_textonly(self, text_prompt):
            
            # Construct the payload
            payload = {
                "model": MODEL_NAME,
                "prompt": text_prompt,
                "stream": False  # Set to True if you want streaming responses
            }

            # Send request
            response = requests.post(OLLAMA_URL, json=payload)

            if response.status_code == 200:
                result = response.json()
                llm_response = result.get("response", "No response received")
                return llm_response
            else:
                print("Error:", response.status_code, response.text)
                
            return None

    def send_request(self, image_path, text_prompt):
        """Sends an image and prompt to the Ollama Llama3.2-Vision model."""
        
        # Encode image
        image_base64 = self.encode_image(image_path)

        # Construct the payload
        payload = {
            "model": MODEL_NAME,
            "prompt": text_prompt,
            "images": [image_base64],  # Send as a list if multiple images are needed
            "stream": False  # Set to True if you want streaming responses
        }

        # Send request
        response = requests.post(OLLAMA_URL, json=payload)

        if response.status_code == 200:
            result = response.json()
            llm_response = result.get("response", "No response received")
            return llm_response
        else:
            print("Error:", response.status_code, response.text)
            

        return None

if __name__ == "__main__":
    # Instantiate the PennyWise class
    pennywise = PennyWise()

    # List of receipt image paths
    folder_path = "/home/deepak/workspace/learn_AI/data/receipts"
    receipt_images = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if (file.lower().endswith('.jpg') or file.lower().endswith('.png'))]

    # Process the receipts
    for receipt_image in receipt_images:
        pennywise.process_receipts(receipt_image)





""" 
    def add_table_entry(self, c1, c2, c3):
        try:
            cursor = self.connection.cursor()

            # SQL insert query
            insert_query = sql.SQL("INSERT INTO grocery_items (c1, c2, c3) VALUES (%s, %s, %s)")
            
            # Execute query
            cursor.execute(insert_query, (c1, c2, c3))

            # Commit changes
            self.connection.commit()
            print("Data inserted successfully.")

        except Exception as e:
            print(f"Error: {e}")
            if conn:
                conn.rollback()
        
        finally:
            # Close cursor and connection
            if cursor:
                cursor.close()
            if conn:
                conn.close()
 """
    