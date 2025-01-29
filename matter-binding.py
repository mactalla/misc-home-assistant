#!/usr/bin/env python3

import argparse
import json
import websocket

messageID = 0

ACLKeys = { 
    "privilege": "1",
    "authMode": "2", 
    "subjects": "3",
    "targets": "4",
    "fabricIndex": "254"
}

BindingKeys = {
    "node": "1",
    "endpoint": "3",
    "cluster": "4",
    "fabricIndex": "254"
}

def next_message_id():
    global messageID
    messageID += 1
    return str(messageID)

def raise_on_error(response):
    if "error_code" in response:
        raise ValueError(f"Error {response['error_code']}: {response.get('details')}")

def normalize_dict(d):
    return {k: v for k, v in d.items() if v is not None}

def match_dict(entry, ref_dict):
    subjectsKey = ACLKeys["subjects"]
    for key in ref_dict:
        if key == subjectsKey:
            continue  # Skip matching the subjects key here
        elif entry.get(str(key)) != ref_dict.get(str(key)):
            return False
    return True

def find_matching_entries(list_of_dicts, ref_dict):
    return [entry for entry in list_of_dicts if match_dict(entry, ref_dict)]

def update_receiver_acl(ws, fabric_id, sender, receiver):
    print("Updating ACL...")
    # Read the existing ACL
    read_acl = {
        "message_id": next_message_id(),
        "command": "read_attribute",
        "args": {
            "node_id": receiver["node"],
            "attribute_path": "0/31/0"
        }
    }
    ws.send(json.dumps(read_acl))

    acl_response = ws.recv()
    acl_data = json.loads(acl_response)
    raise_on_error(acl_data)
    # print(f"Original ACL value: {json.dumps(acl_data['result']['0/31/0'], indent=2)}")
    
    # Validate the expected structure
    if "result" not in acl_data or "0/31/0" not in acl_data["result"]:
        raise ValueError("Missing ACL data or expected result key in response.")

    # Create the new entry to be added
    new_entry = {
        ACLKeys["fabricIndex"]: fabric_id,
        ACLKeys["privilege"]: 3,
        ACLKeys["authMode"]: 2,
        ACLKeys["subjects"]: [sender["node"]],
        ACLKeys["targets"]: None
    }

    # Try to find an exact match for all fields excluding "Subjects"
    matching_entries = find_matching_entries(acl_data["result"]["0/31/0"], new_entry)
    
    if matching_entries:
        # For each matching entry, check if the "Subjects" field contains the sender_id
        for entry in matching_entries:
            if sender["node"] not in entry[ACLKeys["subjects"]]:
                # If the subject is missing, update the entry with the sender_id
                entry[ACLKeys["subjects"]].append(sender["node"])
                print("Expanding existing entry")
                break
        else:
            # If no entries are updated, then no further action is needed
            print("No ACL update needed")
            return
    else:
        # If no matching entries are found, append a new one
        acl_data["result"]["0/31/0"].append(new_entry)

    # Create the message to write the updated ACL
    write_acl_message = {
        "message_id": next_message_id(),
        "command": "write_attribute",
        "args": {
            "node_id": receiver["node"],
            "attribute_path": "0/31/0",
            "value": acl_data["result"]["0/31/0"]
        }
    }

    ws.send(json.dumps(write_acl_message))
    new_acl_resp = ws.recv()
    new_acl_data = json.loads(new_acl_resp)
    raise_on_error(new_acl_data)
    print("ACL updated")

import pdb
def create_binding(ws, fabric_id, sender, receiver):
    print("Creating binding...")
    # pdb.set_trace()
    read_bindings = {
        "message_id": next_message_id(),
        "command": "read_attribute",
        "args": {
            "node_id": sender["node"],
            "attribute_path": f"{sender['endpoint']}/30/0"
        }
    }
    ws.send(json.dumps(read_bindings))

    read_response = ws.recv()
    bindings_data = json.loads(read_response)
    raise_on_error(bindings_data)
    binding_entries = bindings_data.get("result", {}).get(f"{sender['endpoint']}/30/0", [])
    # print(f"Existing Bindings value: {json.dumps(binding_entries, indent=2)}")

    new_binding = {
        BindingKeys["fabricIndex"]: fabric_id,
        BindingKeys["node"]: receiver["node"],
        BindingKeys["endpoint"]: receiver["endpoint"],
        BindingKeys["cluster"]: None
    }

    # Check if the new binding already exists
    if any(normalize_dict(new_binding) == normalize_dict(binding) for binding in binding_entries):
        print("Binding already exists, no update needed")
        return
    
    binding_entries.append(new_binding)

    create_binding = {
        "message_id": next_message_id(),
        "command": "write_attribute",
        "args": {
            "node_id": sender["node"],
            "attribute_path": f"{sender['endpoint']}/30/0",
            "value": binding_entries
        }
    }

    ws.send(json.dumps(create_binding))
    write_response = ws.recv()
    result_data = json.loads(write_response)
    raise_on_error(result_data)
    print("Binding created")

def bind_nodes(url, sender, receiver):
    try:
        ws = websocket.create_connection(url)
        print(f"Connection successful to {url}")

        # Read initial message and save fabric_id locally
        initial_message = ws.recv()
        initial_data = json.loads(initial_message)
        fabric_id = initial_data.get("fabric_id")
        print(f"Fabric ID: {fabric_id}")

        update_receiver_acl(ws, fabric_id, sender, receiver)
        create_binding(ws, fabric_id, sender, receiver)

        ws.close()
    except Exception as e:
        print(f"An error occurred: {e}")

def parse_node_arg(arg):
    """
    Parse the --from and --to arguments into a dictionary with 'node' and 'endpoint'.
    If no endpoint is provided, default to 1.
    """
    parts = arg.split(":")
    if len(parts) == 1:
        return {"node": int(parts[0]), "endpoint": 1}
    elif len(parts) == 2:
        return {"node": int(parts[0]), "endpoint": int(parts[1])}
    else:
        raise ValueError(f"Invalid node argument: {arg}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bind nodes with Matter protocol.")
    parser.add_argument("--from", dest="from_node", required=True, help="Sender node in the format node:endpoint (default endpoint=1)")
    parser.add_argument("--to", required=True, help="Receiver node in the format node:endpoint (default endpoint=1)")
    args = parser.parse_args()

    sender = parse_node_arg(args.from_node)
    receiver = parse_node_arg(args.to)
    url = "ws://homeassistant.local:5580/ws"

    bind_nodes(url, sender, receiver)
