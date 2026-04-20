import csv
import json
import yaml

def generate_hierarchy():
    # Load configuration
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    building_id = cfg['simulation']['building_id']
    floors = cfg['simulation']['floors']
    rooms_per_floor = cfg['simulation']['rooms_per_floor']

    hierarchy_json = {
        "Campus": {
            "type": "Campus",
            "children": {
                f"Building {building_id}": {
                    "type": "Building",
                    "children": {}
                }
            }
        }
    }

    relations_csv_rows = []
    
    # Campus to Building
    relations_csv_rows.append({
        "FromType": "Asset", "FromName": "Campus",
        "RelationType": "Contains", 
        "ToType": "Asset", "ToName": f"Building {building_id}"
    })

    b_node = hierarchy_json["Campus"]["children"][f"Building {building_id}"]["children"]

    for f_idx in range(1, floors + 1):
        f_name = f"Floor {f_idx:02d}"
        b_node[f_name] = {
            "type": "Floor",
            "children": {}
        }

        # Building to Floor
        relations_csv_rows.append({
            "FromType": "Asset", "FromName": f"Building {building_id}",
            "RelationType": "Contains", 
            "ToType": "Asset", "ToName": f_name
        })

        f_node = b_node[f_name]["children"]

        for r_idx in range(1, rooms_per_floor + 1):
            r_name = f"Room {f_idx:02d}-{r_idx:03d}"
            device_id = f"{building_id}-f{f_idx:02d}-r{r_idx:03d}"
            
            f_node[r_name] = {
                "type": "Room",
                "devices": [device_id]
            }

            # Floor to Room
            relations_csv_rows.append({
                "FromType": "Asset", "FromName": f_name,
                "RelationType": "Contains", 
                "ToType": "Asset", "ToName": r_name
            })

            # Room to Device
            relations_csv_rows.append({
                "FromType": "Asset", "FromName": r_name,
                "RelationType": "Contains", 
                "ToType": "Device", "ToName": device_id
            })

    # Export JSON
    with open("asset_hierarchy.json", "w") as jf:
        json.dump(hierarchy_json, jf, indent=4)
    print("Exported asset_hierarchy.json")

    # Export CSV
    with open("asset_relations.csv", "w", newline="") as cf:
        fieldnames = ["FromType", "FromName", "RelationType", "ToType", "ToName"]
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(relations_csv_rows)
    print("Exported asset_relations.csv")

if __name__ == "__main__":
    generate_hierarchy()
