#!/usr/bin/env python3

# Libraries
##############################################################################
from flask import Blueprint, request, jsonify
import pymongo
from datetime import datetime

from Shared.configs import DB_NAME,DB_HOST,DB_PORT,DB_USERNAME,DB_PASSWORD
from Shared.validators import agent_token_required
from Agents.helper_funcs import get_id_by_token
##############################################################################

# Blueprint
##############################################################################
sys_data_bp = Blueprint('system_data_blueprint', __name__)
##############################################################################

# Mongo Configs
##############################################################################
# Replace these values with your MongoDB connection details
mongo_client = pymongo.MongoClient(
    f"mongodb://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
)
db = mongo_client[DB_NAME]
system_data_collection  = db["system_data"]
changelog_collection    = db["changelog"]
##############################################################################


##############################################################################
def compare_and_log_changes(existing_item, new_item, parent_key="", changes={}):
    if isinstance(new_item, dict):
        for key, value in new_item.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            changes = compare_and_log_changes(existing_item.get(key, {}), value, parent_key=full_key, changes=changes)
    elif isinstance(new_item, list):
        for i, item in enumerate(new_item):
            full_key = f"{parent_key}[{i}]"
            changes = compare_and_log_changes(existing_item[i] if i < len(existing_item) else {}, item, parent_key=full_key, changes=changes)
    elif new_item != existing_item:
        changes[parent_key] = {"new_value": new_item, "previous_value": existing_item}
    return changes
##############################################################################

# Routes
##############################################################################

# Save Data
@sys_data_bp.route('/', methods=['POST'])
@agent_token_required
def register():
    # Extract the agent_token from the Authorization header
    agent_token = request.headers.get("Authorization")

    # Get Agent ID by token
    agent_id = get_id_by_token(agent_token)

    # Get Data from Request
    data = request.get_json()

    # Define the unique identifier using the agent_id
    unique_identifier = {"agent_id": agent_id}

    # Find existing document with the same identifier
    existing_document = system_data_collection.find_one(unique_identifier)

    if existing_document:
        # Document with the same identifier exists, check for changes
        changes = compare_and_log_changes(existing_document, data)

        if changes:
            # Log changes to the changelog collection
            changelog_entry = {
                "timestamp": datetime.now(),
                "agent_id": agent_id,
                "changes": changes
            }
            changelog_collection.insert_one(changelog_entry)

            # Update the existing document with changes
            system_data_collection.update_one(unique_identifier, {"$set": data})

        # Update the existing document with changes
        system_data_collection.update_one(unique_identifier, {"$set": existing_document})
    else:
        # Document with the unique identifier doesn't exist, insert the new document
        # Insert the System Data into the System Data Collection
        data["agent_id"] = agent_id
        system_data_collection.insert_one(data)
    
    return jsonify(
        {
            'message': 'Data registered successfully.',
        }
    ), 201
##############################################################################