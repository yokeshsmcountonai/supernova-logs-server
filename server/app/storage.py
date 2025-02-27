
import time
import psycopg2
import requests
import traceback
from db import Execute
from datetime import datetime, timedelta
from typing import List, Tuple,Optional,Dict,Any


db=Execute()

PROMETHEUS_URL = 'http://localhost:9090'

FETCH_QUERY = """
    SELECT CONCAT(mill_name, '-', machine_name) AS machine_name, ip_address
    FROM public.machine_details
    INNER JOIN public.mill_details
    ON mill_details.milldetails_id = machine_details.milldetails_id
    WHERE prometheus_sts = '1';
"""

INSERT_METRICS_QUERY = """
INSERT INTO machine_metrics (machine_name, cpu_usage, ram_usage, temperature, gpu_temperature, voltage, timestamp,device_type)
VALUES (%s, %s, %s, %s, %s, %s, %s,%s)
ON CONFLICT (machine_name,device_type) DO UPDATE
SET cpu_usage = EXCLUDED.cpu_usage,
    ram_usage = EXCLUDED.ram_usage,
    gpu_temperature = EXCLUDED.gpu_temperature,
    voltage = EXCLUDED.voltage,
    temperature = EXCLUDED.temperature,
    timestamp = EXCLUDED.timestamp,
    device_type=EXCLUDED.device_type

"""

INSERT_TIME_METRICS_QUERY = """
INSERT INTO machine_time_metrics (machine_name, cpu_usage, ram_usage, temperature, gpu_temperature, voltage, timestamp,device_type)
VALUES (%s, %s, %s, %s, %s, %s, %s,%s);
"""



def fetch_machine_details(conn) -> List[Tuple[str, str]]:
    """
    Fetches the machine details from the database.

    Executes the SQL query to retrieve machine names and IP addresses
    from the database, where the 'prometheus_sts' is set to '1'.

    Args:
        conn: A psycopg2 connection object to the PostgreSQL database.

    Returns:
        A list of tuples, each containing the machine name and IP address
        (machine_name, ip_address).
    """
    with conn.cursor() as cursor:
        cursor.execute(FETCH_QUERY)
        return cursor.fetchall()

def query_prometheus(mill_name: str, query: str) -> Optional[float]:
    """
    Queries the Prometheus server for the given query and returns the result.

    Sends a GET request to the Prometheus API to execute the provided query. 
    If the query returns valid data, the result is parsed and converted to a float. 
    If no result is returned or an error occurs, None is returned.

    Args:
        mill_name (str): The name of the mill for which the query is being made.
        query (str): The Prometheus query string to execute.

    Returns:
        Optional[float]: The query result as a float if successful, or None if an error occurs
                         or no valid result is found.
    """
    try:
        response = requests.get(f'{PROMETHEUS_URL}/api/v1/query', params={'query': query})
        response.raise_for_status()  
        data = response.json()

        if data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
        else:
            return None
    except requests.RequestException as e:
        print(f"Error querying Prometheus for {mill_name}: {str(e)}")
        return None

def fetch_metrics(mill_name: str, ip: str,device:str) -> Dict[str, Optional[float]]:
    """
    Fetches various system metrics from Prometheus for the specified machine.

    This function queries the Prometheus server for multiple metrics, such as CPU usage,
    RAM usage, storage space, GPU usage, and more. It returns a dictionary of metrics 
    with corresponding values, converting them where necessary (e.g., bytes to GB). 
    If a metric is unavailable, it will be set to None.

    Args:
        mill_name (str): The name of the mill for which the metrics are being fetched.
        ip (str): The IP address of the machine to query the metrics for.

    Returns:
        Dict[str, Optional[float]]: A dictionary containing the fetched metrics, where 
                                     each key is a string representing the metric name,
                                     and the value is either a float or None if the metric is unavailable.
    """
    metrics = {
        "cpu_usage": None,
        "ram_usage": None,
        "gpu_temperature": None,
        "timestamp": None,
        "voltage": None,
        "temperature": None,
        "device_type":device
    }

    var = f'mode="idle",instance="{ip}:9100"'

    

    cpu_usage_query = f"cpu_usage{{device='{device}',group='{mill_name}'}}"
    ram_query = f"ram_usage{{device='{device}',group='{mill_name}'}}"
    gpu_temp_query = f"gpu_temperature{{device='{device}',group='{mill_name}'}}"
    timestamp_query = f"timestamp{{device='{device}',group='{mill_name}'}}"
    voltage_query = f"voltage{{device='{device}',group='{mill_name}'}}"
    temperature_query = f"temperature{{device='{device}',group='{mill_name}'}}"
    print(cpu_usage_query)
    
    try:
        metrics["cpu_usage"] = query_prometheus(mill_name, cpu_usage_query)
        metrics["ram_usage"]  = query_prometheus(mill_name, ram_query)
       
        
        metrics["gpu_temperature"] = query_prometheus(mill_name, gpu_temp_query)
        metrics["voltage"] = query_prometheus(mill_name, voltage_query)
        metrics["temperature"] = query_prometheus(mill_name, temperature_query)
        

        prometheus_timestamp = query_prometheus(mill_name, timestamp_query)
        if prometheus_timestamp:
            metrics["timestamp"] = datetime.fromtimestamp(prometheus_timestamp)
        else:
            metrics["timestamp"] = datetime.now()  

    except Exception as e:
        print(f"Error fetching metrics for {mill_name} ({ip}): {str(e)}")
        traceback.print_exc()

    return metrics



def insert_metrics(conn: psycopg2.extensions.connection, machine_name: str, metrics: Dict[str, Any]) -> None:
    """
    Insert machine metrics into the database, handling unavailable metrics and avoiding conflicts.

    Args:
        conn (psycopg2.extensions.connection): The database connection object.
        machine_name (str): The name of the machine (e.g., 'Mill1-Machine1').
        metrics (Dict[str, Any]): A dictionary containing metric names as keys and their corresponding values.
    """
    cpu_usage = metrics.get("cpu_usage", -1) or -1
    ram_usage = metrics.get("ram_usage", -1) or -1
    gpu_temperature = metrics.get("gpu_temperature", -1) or -1
    temperature = metrics.get("temperature", -1) or -1
    voltage = metrics.get("voltage", -1) or -1
    timestamp = metrics.get("timestamp", datetime.now()) 
    device_type=metrics.get("device_type")
    if isinstance(timestamp, datetime):
        timestamp -= timedelta(hours=5, minutes=30)  # Subtract 5 hours 30 minutes
        timestamp = timestamp.isoformat()  # Convert to ISO format

    print(f"Inserting metrics for {machine_name}: CPU={cpu_usage}, RAM={ram_usage}, Temp={temperature}, Timestamp:{timestamp}")

    try:
        with conn.cursor() as cursor:
          
            cursor.execute(
                INSERT_METRICS_QUERY,
                (
                    machine_name,
                    cpu_usage,
                    ram_usage,
                    temperature,
                    gpu_temperature,
                    voltage,
                    timestamp,
                    device_type
                )
            )

            
            cursor.execute(
                INSERT_TIME_METRICS_QUERY,
                (
                    machine_name,
                    cpu_usage,
                    ram_usage,
                    temperature,
                    gpu_temperature,
                    voltage,
                    timestamp,
                    device_type
                )
            )

        conn.commit()
        print(f" Metrics for {machine_name} inserted successfully.")

    except psycopg2.Error as e:
        print(f"Error inserting metrics for {machine_name}: {e}")
        traceback.print_exc()
        conn.rollback()


def fetch_main() -> None:
    """
    Fetch and insert metrics for machines from the central database into the version control database.
    
    This function establishes a connection to the 'central_database' and fetches machine details. 
    Then, it switches to the 'version_control' database and inserts the fetched metrics for each 
    machine. The process runs continuously in a loop, executing every 10 seconds.
    
    It handles any exceptions that occur during the process and ensures the connection is properly closed.
    
    Returns:
        None
    """

    try:
        while True:
            
            db.change_database('supernova_central')
            conn = db.connect()
            machines = fetch_machine_details(conn)
            devices=["cam1","cam2","cm5"]
            
            for mill_name, ip in machines:
                for device in devices:
                    metrics = fetch_metrics(mill_name, ip,device)
                    print(metrics)
                    insert_metrics(conn, mill_name, metrics)
                    print(f"inserted into db {device}")
            
          
            time.sleep(10)
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
    
    finally:
        if conn:
            conn.close()
        
fetch_main()