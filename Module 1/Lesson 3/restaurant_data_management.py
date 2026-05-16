from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
import json
import os
import shutil
import io
import unittest
from unittest.mock import patch

# Update your restaurant_data_structure_prompt_generation
def restaurant_data_structure_prompt_generation(restaurant_paragraph):
    system_msg = """
You are a data extraction assistant.
Your task is to extract structured restaurant information from a paragraph.
Return ONLY valid JSON. Do not include explanations, markdown, or extra text.
"""

    prompt_txt = f"""
Extract the restaurant information from the paragraph below and return it as JSON.

The JSON should include:
- name
- cuisine
- location
- price_range
- rating
- description
- opening_hours
- contact
- highlights

If a field is not mentioned, use null.
If highlights has multiple values, return them as a list.

Paragraph:
{restaurant_paragraph}
"""

    return system_msg, prompt_txt


# Might need to explain why we are using granite here (cheap)
def llm_model(system_msg, prompt_txt):
    #system_msg: the system message given to the LLM
    #prompt_txt: the user prompt
    
    model_id = "ibm/granite-4-h-small"

    project_id="skills-network"

    credentials = Credentials(
                    url = "https://us-south.ml.cloud.ibm.com"
                    )

    ### 1.1: Define the model by ModelInference
    model = ModelInference(
        credentials=credentials,
        model_id=model_id,
        project_id=project_id
    )
        

    ### 1.2: Define the messages
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt_txt}]
    
    ### 1.3: Get the final response output and return it
    response = model.chat(messages=messages)
    final_response = response["choices"][0]["message"]["content"] 
    return final_response


def JSON_auto_repair_prompts(response, error_message):
    system_msg = """
You are a JSON repair assistant.
Your task is to fix invalid JSON.
Return ONLY valid JSON. Do not include markdown, comments, or explanations.
"""

    prompt_txt = f"""
The following response was supposed to be valid JSON, but it produced this error:

Error:
{error_message}

Invalid JSON:
{response}

Repair it and return only the corrected JSON.
"""

    return system_msg, prompt_txt


def new_data_entry_process(paragraph, itemId):
    system_msg, prompt_txt = restaurant_data_structure_prompt_generation(paragraph)

    response = llm_model(system_msg, prompt_txt)

    try:
        structured_data = json.loads(response)
    except json.JSONDecodeError as e:
        repair_system_msg, repair_prompt_txt = JSON_auto_repair_prompts(
            response,
            str(e)
        )

        repaired_response = llm_model(repair_system_msg, repair_prompt_txt)
        structured_data = json.loads(repaired_response)

    structured_data["itemId"] = itemId

    return structured_data

def load_data(file_path):
    """Load restaurant data from a JSON file."""
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r") as f:
        return json.load(f)


def save_data(data, file_path, backup_path):
    """Save restaurant data safely and create a backup first."""
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


def show_restaurant_card(res, index):
    """Display one restaurant record."""
    print(f"\n--- Restaurant Record #{index} ---")
    for key, value in res.items():
        print(f"{key}: {value}")
    

def manage_restaurants(file_path, backup_path):
    while True:
        data = load_data(file_path)
        print(f"\n🏨 RESTAURANT DATABASE | Records: {len(data)}")
        print("1. Browse All (Names)")
        print("2. View Detailed Record")
        print("3. Add New Restaurant")
        print("4. Edit Restaurant Info")
        print("5. Delete Restaurant")
        print("6. Exit")
        
        choice = input("\nAction: ")

        if choice == '1':
            print("\n--- Current Listings ---")

            for index, res in enumerate(data):
                print(f"{index}: {res.get('name', 'N/A')}")

        elif choice == '2':
            index = int(input("Enter record index: "))

            if 0 <= index < len(data):
                show_restaurant_card(data[index], index)
            else:
                print("Invalid index.")

        elif choice in ['3', '4', '5']:
            print("\n 🚨 SECURITY WARNING: You are entering write-mode.")
            print("Changes will be saved to the database immediately.")
            confirm = input("Are you sure? (type 'yes' to proceed): ").lower()

            if confirm != 'yes':
                print("Operation cancelled.")
                continue

            if choice == '3':  # ADD NEW DATA
                itemId = 100000 + len(data) + 1

                paragraph = input("Enter new restaurant description: ")

                new_restaurant = new_data_entry_process(paragraph, itemId)

                data.append(new_restaurant)

                save_data(data, file_path, backup_path)

                print("✅ Restaurant added.")

            elif choice == '4':  # EDIT DATA
                index = int(input("Enter record index to edit: "))

                if 0 <= index < len(data):
                    record = data[index]

                    for key in record:
                        current_value = record[key]
                        new_value = input(f"{key} [{current_value}]: ")

                        if new_value != "":
                            record[key] = new_value

                    save_data(data, file_path, backup_path)
                    print("✅ Record updated.")
                else:
                    print("Invalid index.")

            elif choice == '5':  # DELETE DATA
                index = int(input("Enter record index to delete: "))

                if 0 <= index < len(data):
                    data.pop(index)
                    save_data(data, file_path, backup_path)
                    print("✅ Record deleted.")
                else:
                    print("Invalid index.")

        elif choice == '6': # EXIT
            break
        else:
            print("Invalid input.")


class TestRestaurantDatabase(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary clean database for testing."""
        self.test_file = 'structured_restaurant_data_unit_test.json'
        self.test_file_backup = 'structured_restaurant_data_unit_test.json.bak'
        self.initial_data = [{"name": "Test Cafe", "location": "Test City"}]
        with open(self.test_file, 'w') as f:
            json.dump(self.initial_data, f)

    def tearDown(self):
        """Clean up the test file after tests."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

        if os.path.exists(self.test_file_backup):
            os.remove(self.test_file_backup)

    @patch('builtins.input')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_add_and_delete_restaurant_success(self, mock_stdout, mock_input):
        """
        Test Scenario: Add a new restaurant.
        Inputs: '3' (Add), 'yes' (Confirm), 'New Burger Joint', '6' (Exit)
        """
        # We mock the sequence of user inputs
        mock_restaurant = 'The Copper Sprout is a high-concept, Modern Appalachian farm-to-table destination that blends an industrial-chic aesthetic with rustic forest charm, featuring reclaimed wood and amber lighting to create a sophisticated yet cozy vibe. Priced in the $$ category, the menu celebrates seasonal foraging and local heritage, headlined by signature dishes like Cast-Iron Smoked Trout with pickled fiddlehead ferns and hand-foraged Wild Mushroom Risotto with aged goat cheese. The experience is designed to be intimate and earthy, making it a premier spot for those seeking high-quality, smokehouse-influenced cuisine in a refined, atmospheric setting.'
        mock_input.side_effect = ['3', 'yes', mock_restaurant, '6']
        
        # Run the app
        try:
            manage_restaurants(self.test_file, self.test_file_backup)
        except SystemExit:
            pass # Handle exit if your script uses sys.exit()

        # Check if the data was actually saved
        with open(self.test_file, 'r') as f:
            data = json.load(f)
        
        print(data)
        self.assertEqual(len(data), 2)
        self.assertIn("✅ Restaurant added.", mock_stdout.getvalue())

        mock_input.side_effect = ['5', 'yes', 1, '6']
        
        # Run the app
        try:
            manage_restaurants(self.test_file, self.test_file_backup)
        except SystemExit:
            pass # Handle exit if your script uses sys.exit()

        # Check if the data was actually saved
        with open(self.test_file, 'r') as f:
            data = json.load(f)
        
        print(data)
        self.assertEqual(len(data), 1)

    @patch('builtins.input')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_delete_security_cancel(self, mock_stdout, mock_input):
        """
        Test Scenario: Try to delete but say 'no' to security warning.
        Inputs: '5' (Delete), 'no' (Cancel), '6' (Exit)
        """
        mock_input.side_effect = ['5', 'no', '6']
        
        manage_restaurants(self.test_file, self.test_file_backup)
        
        with open(self.test_file, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1) # Data should remain unchanged
        self.assertIn("Operation cancelled.", mock_stdout.getvalue())
		

#TESTING
#if __name__ == "__main__":
#    unittest.main() # Unit Test
	# manage_restaurants(FILEPATH, BACKUP_PATH) # Actual UI Call


FILEPATH = "structured_restaurant_data.json"
BACKUP_PATH = "structured_restaurant_data_backup.json"

# RUN THE UI
if __name__ == "__main__":
    manage_restaurants(FILEPATH, BACKUP_PATH)