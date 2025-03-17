import time
import psycopg2
import requests
import traceback
from db import Execute
from datetime import datetime, timedelta
from typing import List, Tuple,Optional,Dict,Any


db=Execute()

PROMETHEUS_URL = 'http://100.121.194.26:9090'

FETCH_QUERY = """
    SELECT CONCAT(mill_name, '-', machine_name) AS machine_name, ip_address
    FROM public.machine_details
    INNER JOIN public.mill_details
    ON mill_details.milldetails_id = machine_details.milldetails_id
    WHERE prometheus_sts = '1';
"""

INSERT_METRICS_QUERY = """
INSERT INTO machine_metrics (
    machine_name, cpu_usage, ram_usage, temperature, 
    gpu_temperature, voltage, timestamp, device_type
) 
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (machine_name, device_type) 
DO UPDATE 
SET cpu_usage = EXCLUDED.cpu_usage,
    ram_usage = EXCLUDED.ram_usage,
    gpu_temperature = EXCLUDED.gpu_temperature,
    voltage = EXCLUDED.voltage,
    temperature = EXCLUDED.temperature,
    timestamp = EXCLUDED.timestamp,
    device_type = EXCLUDED.device_type;

"""

INSERT_TIME_METRICS_QUERY = """
INSERT INTO machine_time_metrics (machine_name, cpu_usage, ram_usage, temperature, gpu_temperature, voltage, timestamp,device_type)
VALUES (%s, %s, %s, %s, %s, %s, %s,%s);
"""

INSERT_COREFPR_TIME_METRICS_QUERY = """
INSERT INTO corefpr_time_metrics (
    mill_name, core_to_camera, camera_to_core, core_to_infer, 
    infer_to_ml, ml_to_core, core_to_alarm, alarm_to_core, 
    timestamp, device_type
) 
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (mill_name, device_type, timestamp) 
DO UPDATE 
SET core_to_camera = EXCLUDED.core_to_camera,
    camera_to_core = EXCLUDED.camera_to_core,
    core_to_infer = EXCLUDED.core_to_infer,
    infer_to_ml = EXCLUDED.infer_to_ml,
    ml_to_core = EXCLUDED.ml_to_core,
    core_to_alarm = EXCLUDED.core_to_alarm,
    alarm_to_core = EXCLUDED.alarm_to_core;
"""

INSERT_COREFPR_METRICS_QUERY = """
INSERT INTO corefpr_metrics (
    mill_name, core_to_camera, camera_to_core, core_to_infer, 
    infer_to_ml, ml_to_core, core_to_alarm, alarm_to_core, 
    timestamp, device_type
) 
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (mill_name, device_type) 
DO UPDATE 
SET core_to_camera = EXCLUDED.core_to_camera,
    camera_to_core = EXCLUDED.camera_to_core,
    core_to_infer = EXCLUDED.core_to_infer,
    infer_to_ml = EXCLUDED.infer_to_ml,
    ml_to_core = EXCLUDED.ml_to_core,
    core_to_alarm = EXCLUDED.core_to_alarm,
    alarm_to_core = EXCLUDED.alarm_to_core,
    timestamp = EXCLUDED.timestamp;

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
    metrics = {
        "cpu_usage": None,
        "ram_usage": None,
        "gpu_temperature": None,
        "m_timestamp": None,
        "voltage": None,
        "temperature": None,
        "device_type":device
    }

    var = f'mode="idle",instance="{ip}:9100"'

    

    cpu_usage_query = f"cpu_usage{{device='{device}',group='{mill_name}'}}"
    ram_query = f"ram_usage{{device='{device}',group='{mill_name}'}}"
    gpu_temp_query = f"gpu_temperature{{device='{device}',group='{mill_name}'}}"
    timestamp_query = f"m_timestamp{{device='{device}',group='{mill_name}'}}"
    
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
            metrics["m_timestamp"] = datetime.fromtimestamp(prometheus_timestamp).replace(microsecond=0)
        else:
            metrics["m_timestamp"] = datetime.now().replace(microsecond=0)

     

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
    m_timestamp = metrics.get("m_timestamp") 
    device_type=metrics.get("device_type")
    # if isinstance(timestamp, datetime):
    #     timestamp -= timedelta(hours=5, minutes=30)  # Subtract 5 hours 30 minutes
    #     timestamp = timestamp.isoformat()  # Convert to ISO format

    print(f"Inserting metrics for {machine_name}: CPU={cpu_usage}, RAM={ram_usage}, Temp={temperature}, Timestamp:{m_timestamp}")

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
                    m_timestamp,
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
                    m_timestamp,
                    device_type
                )
            )

        conn.commit()
        print(f" Metrics for {machine_name} inserted successfully.")

    except psycopg2.Error as e:
        print(f"Error inserting metrics for {machine_name}: {e}")
        traceback.print_exc()
        conn.rollback()



def fetch_details(mill_name: str, ip: str, device: str) -> List[Dict[str, Optional[float]]]:
    metrics_list = []
    metric_names = [
        "core_to_camera", "camera_to_core", "core_to_infer", "infer_to_ml",
        "ml_to_core", "core_to_alarm", "alarm_to_core", "cf_timestamp"
    ]

    try:
        for idx in range(100): 
            metrics = {metric: None for metric in metric_names}
            metrics["device_type"] = device
            metrics["id"] = idx  
            
            
            queries = {
                metric: f"{metric}{{device='{device}', group='{mill_name}', id='{idx}'}}"
                for metric in metric_names
            }
            
            for metric, query in queries.items():
                
                result = query_prometheus(mill_name, query)
                if result is not None:
                    metrics[metric] = result

            
            if metrics["cf_timestamp"]:
                metrics["cf_timestamp"] = datetime.fromtimestamp(metrics["cf_timestamp"]).replace(microsecond=0)
            else:
                metrics["cf_timestamp"] = datetime.now().replace(microsecond=0)


        
            metrics_list.append(metrics)  

    except Exception as e:
        print(f"Error fetching metrics for {mill_name} ({ip}): {str(e)}")
        traceback.print_exc()

    return metrics_list




def insert_details(conn: psycopg2.extensions.connection,mill_name: str,ip: str,device: str,metrics_list: List[Dict[str, Optional[float]]]) -> None:
    """
    Insert multiple Prometheus-fetched metrics into the database, handling unavailable metrics and avoiding conflicts.

    Args:
        conn (psycopg2.extensions.connection): The database connection object.
        mill_name (str): The name of the mill.
        ip (str): The IP address of the device.
        device (str): The name of the device.
        metrics_list (List[Dict[str, Optional[float]]]): A list of dictionaries, each containing metric values.
    """
    try:
        with conn.cursor() as cursor:
            for metrics in metrics_list:
                device_type = metrics.get("device_type", device)
                cf_timestamp = metrics.get("cf_timestamp")
                record_id = metrics.get("id", -1)  
                
              
                processed_values = {
                    key: (metrics.get(key, -1) if metrics.get(key) not in (None, "") else -1)
                    for key in [
                        "core_to_camera", "camera_to_core", "core_to_infer",
                        "infer_to_ml", "ml_to_core", "core_to_alarm", "alarm_to_core"
                    ]
                }

               
                print(f"Inserting metrics for {mill_name} ({ip}) - ID: {record_id}, Timestamp: {cf_timestamp}")

               
                cursor.execute(
                    INSERT_COREFPR_METRICS_QUERY,
                    (
                        mill_name, processed_values["core_to_camera"], processed_values["camera_to_core"],
                        processed_values["core_to_infer"], processed_values["infer_to_ml"],
                        processed_values["ml_to_core"], processed_values["core_to_alarm"],
                        processed_values["alarm_to_core"], cf_timestamp, device_type
                    )
                )

                cursor.execute(
                    INSERT_COREFPR_TIME_METRICS_QUERY,
                    (
                        mill_name, processed_values["core_to_camera"], processed_values["camera_to_core"],
                        processed_values["core_to_infer"], processed_values["infer_to_ml"],
                        processed_values["ml_to_core"], processed_values["core_to_alarm"],
                        processed_values["alarm_to_core"], cf_timestamp, device_type
                    )
                )

        conn.commit()
        print(f"Successfully inserted {len(metrics_list)} records for {mill_name} ({ip}).")

    except psycopg2.Error as e:
        print(f"Error inserting metrics for {mill_name} ({ip}): {e}")
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
            cameras=["cam1","cam2"]
            
            for mill_name, ip in machines:
                print('##########################')
                for device in devices:
                    metrics = fetch_metrics(mill_name, ip,device)
                    print(metrics)
                    insert_metrics(conn, mill_name, metrics)
                    print(f"inserted into db {device}")
                print('==========================================')
                for camera in cameras:
                    details=fetch_details(mill_name,ip,camera)
                    print(details)
                    insert_details(conn,mill_name,ip,camera,details)
                    print(f"inserted into db {camera}")
            time.sleep(10)
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
    
    finally:
        if conn:
            conn.close()
        
fetch_main()


