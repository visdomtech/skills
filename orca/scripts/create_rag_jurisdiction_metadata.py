import json
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 create_rag_jurisdiction_metadata.py <regulations_cache> <documents_cache>")
        sys.exit(1)

    reg_path = sys.argv[1]
    doc_path = sys.argv[2]

    # Load data
    with open(reg_path, 'r') as f:
        reg_data = json.load(f)
    
    with open(doc_path, 'r') as f:
        doc_data = json.load(f)

    regulations = reg_data.get('regulations', [])
    documents = doc_data.get('documents', [])

    # Filter included regulations
    included_regs = [r for r in regulations if r.get('included')]
    print(f"Found {len(included_regs)} included regulations.")

    # Build document lookup map (filename -> rag_file_name)
    doc_map = {}
    for doc in documents:
        fname = doc.get('filename')
        rag_name = doc.get('rag_file_name')
        if fname and rag_name:
            doc_map[fname] = rag_name

    matches = []
    missing_count = 0

    for reg in included_regs:
        jurisdiction_code = reg.get('jurisdiction', {}).get('code')
        filenames = reg.get('filenames', [])
        
        if not jurisdiction_code:
            continue

        for fname in filenames:
            rag_name = doc_map.get(fname)
            if rag_name:
                matches.append({
                    "ragFileName": rag_name,
                    "entries": [
                        {"key": "jurisdiction_code", "valueStr": jurisdiction_code}
                    ]
                })
            else:
                missing_count += 1

    # Generate batches of 200
    batch_size = 200
    total_batches = (len(matches) + batch_size - 1) // batch_size
    
    print(f"Total matches found: {len(matches)}")
    print(f"Missing documents: {missing_count}")
    print(f"Generating {total_batches} batch files...")

    output_dir = os.path.dirname(doc_path) # Save batches next to input
    
    for i in range(0, len(matches), batch_size):
        batch_num = i // batch_size + 1
        batch_content = {
            "files": matches[i:i + batch_size]
        }
        
        batch_file = os.path.join(output_dir, f"rag_meta_batch_{batch_num}.json")
        with open(batch_file, 'w') as f:
            json.dump(batch_content, f, indent=2)
        
        print(f"Created {batch_file} with {len(batch_content['files'])} entries.")

if __name__ == "__main__":
    main()
