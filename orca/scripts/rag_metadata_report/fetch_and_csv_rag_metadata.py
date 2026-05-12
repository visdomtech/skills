#!/usr/bin/env python3
"""
Fetch RAG metadata for all documents in the saved JSON and construct a CSV.
This script is designed to be run by an agent that has access to MCP tools,
or it can be adapted to use an MCP client library directly.
"""

import json
import csv
import os
from typing import List, Dict, Any

def main():
    # Load documents
    with open('orca/assets/workspace_1_repo_6_documents.json', 'r') as f:
        data = json.load(f)
    
    docs = data.get('documents', [])
    
    # Prepare CSV rows
    output_file = 'orca/assets/rag_metadata_report.csv'
    fieldnames = ['document_id', 'filename', 'rag_file_name', 'status', 'jurisdiction_code', 'category', 'other_metadata']
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for d in docs:
            rag_file_name = d.get('rag_file_name')
            if not rag_file_name:
                continue
                
            # In a real execution environment, we would call list_rag_metadata here.
            # For this script, we will leave placeholders or use mock data if running locally.
            # The agent should replace this part with actual tool calls.
            
            row = {
                'document_id': d.get('document_id'),
                'filename': d.get('filename'),
                'rag_file_name': rag_file_name,
                'status': d.get('status'),
                'jurisdiction_code': '',
                'category': '',
                'other_metadata': ''
            }
            writer.writerow(row)
            
    print(f"CSV structure created at {output_file} with {len(docs)} rows.")
    print("To populate metadata, this script must be run in an environment with MCP tool access.")

if __name__ == "__main__":
    main()
