import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Carrega variáveis do .env (somente no ambiente local)
load_dotenv()

# Configurações do banco de dados
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Pegando usuário e senha de leitura/escrita das variáveis de ambiente
READ_USER = os.getenv("DB_READ_USER")
READ_PASS = os.getenv("DB_READ_PASS")

WRITE_USER = os.getenv("DB_WRITE_USER")
WRITE_PASS = os.getenv("DB_WRITE_PASS")

# Criar pool de conexões para leitura
read_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=2,
    maxconn=200,
    user=READ_USER,
    password=READ_PASS,
    connect_timeout=5,
    **DB_CONFIG
)

# Criar pool de conexões para escrita
write_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=150,
    user=WRITE_USER,
    password=WRITE_PASS,
    **DB_CONFIG
)








import psycopg2
import os
import sys
import locale

# Configuração de codificação
print("Codificação padrão do terminal:", locale.getpreferredencoding())
print("Codificação de stdout:", sys.stdout.encoding)
print("Codificação de stderr:", sys.stderr.encoding)

# Reconfigura a codificação padrão de saída para UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
# Define UTF-8 como padrão
os.environ["PYTHONIOENCODING"] = "utf-8"


UPD_USER = os.getenv("DB_UPD_USER")
UPD_PASS = os.getenv("DB_UPD_PASS")


# Função para conectar ao banco
def connect():
    try:
        conn = psycopg2.connect(
            user=UPD_USER,                # Usuário do banco de dados
            password=UPD_PASS,
            client_encoding="UTF8",
            **DB_CONFIG
        )
        print("Conexão estabelecida com sucesso.")
        return conn
    except Exception as e:
        print("Erro ao conectar ao banco:", e)
        return None






def get_read_connection():
    return read_pool.getconn()

def get_write_connection():
    return write_pool.getconn()

def release_connection(conn):
    if conn:
        try:
            if conn.info.user == READ_USER:
                read_pool.putconn(conn)
            elif conn.info.user == WRITE_USER:
                write_pool.putconn(conn)
        except Exception as e:
            print(f"Erro ao devolver conexão ao pool: {e}")
