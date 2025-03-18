import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
from dotenv import load_dotenv

def connect():
    # Obter a URL do banco de dados da variável de ambiente
    DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL")
    
    if not DATABASE_PUBLIC_URL:
        raise ValueError("A variável de ambiente DATABASE_PUBLIC_URL não está definida.")
    
    # Parse a URL do banco de dados
    result = urlparse(DATABASE_PUBLIC_URL)
    
    # Extrai os componentes da URL
    username = result.username
    password = result.password
    database = result.path[1:]  # Remove a barra inicial do caminho
    hostname = result.hostname
    port = result.port

    # Cria a string de conexão
    conn_string = f"dbname='{database}' user='{username}' host='{hostname}' password='{password}' port='{port}'"
    
    # Conecta ao banco de dados
    try:
        conn = psycopg2.connect(conn_string)
        print("Conexão estabelecida com sucesso!")
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None