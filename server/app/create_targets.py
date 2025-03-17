# import json
# import psycopg2
# import os 

# # Database connection parameters
# DB_HOST = "localhost"
# DB_PORT = "5432"
# DB_NAME = "supernova_central"
# DB_USER = "postgres"
# DB_PASSWORD = "55555"

# FETCH_QUERY = """
#     SELECT CONCAT(mill_name, '-', machine_name) AS machine_name, ip_address
#     FROM public.machine_details
#     INNER JOIN public.mill_details
#     ON mill_details.milldetails_id = machine_details.milldetails_id
#     WHERE prometheus_sts = '1' ;
# """


# def fetch_machines():
#     """
#     Fetch mill names and IP addresses from the database.

#     :return: A list of tuples (mill_name, ip_address)
#     """
#     try:
        
#         with psycopg2.connect(
#                 host=DB_HOST,
#                 port=DB_PORT,
#                 dbname=DB_NAME,
#                 user=DB_USER,
#                 password=DB_PASSWORD
#         ) as connection:
#             with connection.cursor() as cursor:
#                 cursor.execute(FETCH_QUERY)
#                 return cursor.fetchall()
#     except Exception as e:
#         print(f"Error fetching machine details: {e}")
#         return []


# def generate_target_data(rows, port):
#     """
#     Generate target data for exporters based on IP and port.

#     :param rows: List of tuples (mill_name, ip_address)
#     :param port: The port number for the exporter
#     :return: A list of target dictionaries
#     """
#     print(rows)
#     return [
#         {
#             "targets": [f"{ip_address}:{port}"],
#             "labels": {
#                 "group": mill_name
#             }
#         }

#         for mill_name, ip_address in rows  
#     ]


# def write_json_file(filename, data):
#     """
#     Write the data to a JSON file.

#     :param filename: The name of the file to write to
#     :param data: The data to write to the file
#     """
#     try:
#         with open(filename, 'w') as file:
#             json.dump(data, file, indent=2)
#         print(f"{filename} created successfully.")
#     except Exception as e:
#         print(f"Error writing {filename}: {e}")


# def create_targets_files():
#     """
#     Create the Prometheus target files for Node Exporter, GPU Exporter, and Docker Exporter.
#     """
#     try:
#         rows = fetch_machines()
#         if not rows:
#             print("No machine details found, exiting.")
#             return
#         print(rows)
#         node_targets = generate_target_data(rows, 9100)  
       

       
#         os.makedirs('/tmp/kniti/Desktop/central_monitor/',exist_ok=True)
#         write_json_file(f'/tmp/kniti/Desktop/central_monitor/targets.json', node_targets)
        

#     except Exception as e:
#         print(f"Error creating targets files: {e}")


# if __name__ == "__main__":
#     create_targets_files()




import json
import psycopg2
import os

# Database connection parameters
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "supernova_central"
DB_USER = "postgres"
DB_PASSWORD = "55555"

FETCH_QUERY = """
    SELECT CONCAT(mill_name, '-', machine_name) AS machine_name, ip_address
    FROM public.machine_details
    INNER JOIN public.mill_details
    ON mill_details.milldetails_id = machine_details.milldetails_id
    WHERE prometheus_sts = '1';
"""

def fetch_machines():
    """
    Fetch mill names and IP addresses from the database.

    :return: A list of tuples (mill_name, ip_address)
    """
    try:
        with psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(FETCH_QUERY)
                rows = cursor.fetchall()
                print(f"Fetched from DB: {rows}")  # Debugging line
                return rows
    except Exception as e:
        print(f"Error fetching machine details: {e}")
        return []

def generate_target_data(rows, port):
    """
    Generate target data for exporters based on IP and port.

    :param rows: List of tuples (mill_name, ip_address)
    :param port: The port number for the exporter
    :return: A list of target dictionaries
    """
    target_data = [
        {
            "targets": [f"{ip_address}:{port}"],
            "labels": {
                "group": mill_name
            }
        }
        for mill_name, ip_address in rows
    ]
    print("Generated target data:", json.dumps(target_data, indent=2))  # Debugging line
    return target_data

def write_json_file(filename, data):
    """
    Write the data to a JSON file.

    :param filename: The name of the file to write to
    :param data: The data to write to the file
    """
    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=2)
            file.flush()  # Ensure buffer is written
            os.fsync(file.fileno())  # Force write to disk
        print(f"{filename} created successfully.")
    except Exception as e:
        print(f"Error writing {filename}: {e}")

def create_targets_files():
    """
    Create the Prometheus target files for Node Exporter.
    """
    try:
        rows = fetch_machines()
        if not rows:
            print("No machine details found, exiting.")
            return

        node_targets = generate_target_data(rows, 9100)

        # Ensure the directory exists
        target_directory = '/tmp/kniti/Desktop/central_monitor/'
        os.makedirs(target_directory, exist_ok=True)

        # Write the target data to JSON
        target_file = os.path.join(target_directory, 'targets.json')
        write_json_file(target_file, node_targets)

    except Exception as e:
        print(f"Error creating targets files: {e}")

if __name__ == "__main__":
    create_targets_files()
