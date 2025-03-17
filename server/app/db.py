import psycopg2
import traceback
from typing import List, Dict, Optional


class Execute:
    def __init__(self, database: str = "supernova_central"):
        self.keepalive_kwargs = {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 5,
            "keepalives_count": 5,
        }
        self.database = database
        self.conn = self.connect()



    def select(self, query: str) -> Optional[List[Dict[str, str]]]:
        """Executes a SELECT query and returns the results as a list of dictionaries."""
        try:
            cur = self.conn.cursor()
            cur.execute(query)
            rows = [
                dict((cur.description[i][0], value) for i, value in enumerate(row))
                for row in cur.fetchall()
            ]
            cur.close()
            return rows
        except psycopg2.OperationalError as e:
            self.conn = self.connect()
            traceback.print_exc()
            return None
        except Exception as e:
            traceback.print_exc()
            return False

    def change_database(self, database: str) -> None:
        """Changes the database and reconnects."""
        self.database = database
        self.conn = self.connect()

    def connect(self) -> psycopg2.extensions.connection:
        """Establishes a connection to the PostgreSQL database."""
        conn = psycopg2.connect(
            database=self.database,
            user="postgres",
            password="55555",
            host="localhost",
            port="5432",
            **self.keepalive_kwargs,
        )
        conn.autocommit = True
        return conn


class ClientSideDb:
    def __init__(self) -> None:
        """Initializes the ClientSideDb with an Execute instance."""
        self.execute = Execute()

    def mill_machine_name(self) -> List[Dict[str, str]]:
        """Fetches mill and machine details from the database."""
        try:
            self.execute.change_database('central_database')

            query = """
                SELECT *
                FROM public.mill_details
                INNER JOIN public.machine_details
                ON mill_details.milldetails_id = machine_details.milldetails_id
                WHERE prometheus_sts = '1'
                ORDER BY mill_details.milldetails_id ASC, machine_details.machinedetail_id ASC
            """
            result = self.execute.select(query)
            return result if result else []
        except Exception as e:
            traceback.print_exc()
            return []
    def connect(self) -> psycopg2.extensions.connection:
        """Establishes a connection to the PostgreSQL database."""
        conn = psycopg2.connect(
            database=self.database,
            user="postgres",
            password="55555",
            host="localhost",
            port="5432",
            **self.keepalive_kwargs,
        )
        conn.autocommit = True
        return conn