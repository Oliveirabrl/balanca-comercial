import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
from datetime import datetime

# Função para inicializar o driver do Selenium com configurações para Streamlit Cloud
def initialize_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Modo headless para ambientes sem interface gráfica
    chrome_options.add_argument("--no-sandbox")  # Necessário para ambientes Linux como o Streamlit Cloud
    chrome_options.add_argument("--disable-dev-shm-usage")  # Evita problemas de recursos em contêineres
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # Evita detecção de bots

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        st.write("✅ ChromeDriver inicializado com sucesso.")
        return driver
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o ChromeDriver: {str(e)}")
        return None

# Função para extrair dados da página
def extract_data():
    url = "https://balanca.economia.gov.br/balanca/pg_principal_bc/principais_resultados.html"
    st.write(f"📡 Acessando a URL: {url}")
    
    driver = initialize_driver()
    if driver is None:
        st.error("🚫 Falha ao inicializar o driver. Não é possível prosseguir.")
        return None, None

    try:
        st.write("⏳ Carregando a página...")
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(5)  # Espera adicional para garantir que a página carregue completamente
        html = driver.page_source
        st.write(f"✅ Página carregada com sucesso. Tamanho do HTML: {len(html)} bytes")
    except Exception as e:
        st.error(f"❌ Erro ao acessar a página: {str(e)}")
        driver.quit()
        return None, None
    finally:
        driver.quit()

    # Parsing do HTML
    st.write("🔍 Analisando o HTML...")
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    if len(tables) < 2:
        st.error(f"🚫 Esperava-se 2 tabelas, mas foram encontradas {len(tables)}. Verifique se a estrutura da página mudou.")
        return None, None
    st.write(f"✅ Encontradas {len(tables)} tabelas.")

    # Extrair tabelas
    weekly_table = tables[0]
    monthly_table = tables[1]

    # Função auxiliar para extrair dados de tabelas
    def extract_table_data(table, table_name):
        st.write(f"📋 Extraindo dados da tabela: {table_name}")
        rows = table.find_all('tr')
        if not rows:
            st.error(f"🚫 Nenhuma linha encontrada na tabela {table_name}.")
            return [], []

        headers = [col.text.strip() for col in rows[0].find_all(['th', 'td'])]
        if not headers:
            st.error(f"🚫 Nenhum cabeçalho encontrado na tabela {table_name}.")
            return [], []

        data = []
        for row in rows[1:]:
            cols = [col.text.strip() for col in row.find_all('td')]
            if not cols:
                continue
            while len(cols) < len(headers):
                cols.append("")
            if len(cols) > len(headers):
                cols = cols[:len(headers)]
            data.append(cols)
        st.write(f"✅ Extraídos {len(data)} registros da tabela {table_name}.")
        return headers, data

    weekly_headers, weekly_data = extract_table_data(weekly_table, "Semanal")
    monthly_headers, monthly_data = extract_table_data(monthly_table, "Mensal")

    if not weekly_data or not monthly_data:
        st.error("🚫 Dados não encontrados nas tabelas.")
        return None, None

    # Criar DataFrames
    st.write("📊 Criando DataFrames...")
    weekly_df = pd.DataFrame(weekly_data, columns=weekly_headers)
    monthly_df = pd.DataFrame(monthly_data, columns=monthly_headers)

    # Renomear colunas
    weekly_df.rename(columns={
        weekly_headers[0]: 'Período',
        'Exportações': 'EXPORTAÇÕES Valor',
        'Importações': 'IMPORTAÇÕES Valor'
    }, inplace=True)
    monthly_df.rename(columns={
        monthly_headers[0]: 'Mês',
        'Exportações': 'EXPORTAÇÕES Valor',
        'Importações': 'IMPORTAÇÕES Valor'
    }, inplace=True)

    # Limpar e converter valores numéricos
    st.write("🧹 Limpando e convertendo valores numéricos...")
    for df in [weekly_df, monthly_df]:
        for col in df.columns:
            if 'valor' in col.lower():
                try:
                    df[col] = pd.to_numeric(df[col].str.replace('.', '').str.replace(',', '.'), errors='coerce')
                except Exception as e:
                    st.error(f"❌ Erro ao converter a coluna '{col}': {str(e)}")
                    return None, None

    # Adicionar data de atualização
    update_date = datetime.now()
    weekly_df['Data'] = update_date
    monthly_df['Data'] = update_date

    st.write("✅ Dados extraídos e processados com sucesso!")
    return weekly_df, monthly_df

# Função para atualizar dados históricos
def update_historical_data(weekly_df, monthly_df):
    weekly_file = 'historico_semanais.csv'
    monthly_file = 'historico_mensais.csv'

    # Inicializar arquivos CSV se não existirem
    if not os.path.exists(weekly_file):
        pd.DataFrame(columns=['Período', 'EXPORTAÇÕES Valor', 'IMPORTAÇÕES Valor', 'Data']).to_csv(weekly_file, index=False)
    if not os.path.exists(monthly_file):
        pd.DataFrame(columns=['Mês', 'EXPORTAÇÕES Valor', 'IMPORTAÇÕES Valor', 'Data']).to_csv(monthly_file, index=False)

    # Atualizar arquivos
    for file, df in [(weekly_file, weekly_df), (monthly_file, monthly_df)]:
        historical = pd.read_csv(file)
        historical = pd.concat([historical, df]).drop_duplicates(subset=[df.columns[0], 'Data'])
        historical.to_csv(file, index=False)

    return pd.read_csv(weekly_file), pd.read_csv(monthly_file)

# Dashboard no Streamlit
st.title("Dashboard Balança Comercial")
st.markdown("Visualize os dados de exportações e importações da Balança Comercial Brasileira.")

if st.button("Atualizar Dados"):
    with st.spinner("Extraindo dados..."):
        weekly_df, monthly_df = extract_data()
        if weekly_df is not None and monthly_df is not None:
            weekly_historical, monthly_historical = update_historical_data(weekly_df, monthly_df)
            st.success("Dados atualizados!")
        else:
            st.error("Falha na atualização.")
else:
    # Carregar dados históricos
    weekly_historical = pd.read_csv('historico_semanais.csv') if os.path.exists('historico_semanais.csv') else pd.DataFrame()
    monthly_historical = pd.read_csv('historico_mensais.csv') if os.path.exists('historico_mensais.csv') else pd.DataFrame()

# Calcular variação percentual
if not weekly_historical.empty and pd.api.types.is_numeric_dtype(weekly_historical['EXPORTAÇÕES Valor']):
    weekly_historical['Variação % Exportações'] = weekly_historical['EXPORTAÇÕES Valor'].pct_change() * 100
if not monthly_historical.empty and pd.api.types.is_numeric_dtype(monthly_historical['EXPORTAÇÕES Valor']):
    monthly_historical['Variação % Exportações'] = monthly_historical['EXPORTAÇÕES Valor'].pct_change() * 100

# Exibir tabelas
st.subheader("Dados Semanais")
if not weekly_historical.empty:
    st.dataframe(weekly_historical[['Período', 'EXPORTAÇÕES Valor', 'IMPORTAÇÕES Valor', 'Variação % Exportações', 'Data']])
else:
    st.warning("Nenhum dado semanal disponível.")

st.subheader("Dados Mensais")
if not monthly_historical.empty:
    st.dataframe(monthly_historical[['Mês', 'EXPORTAÇÕES Valor', 'IMPORTAÇÕES Valor', 'Variação % Exportações', 'Data']])
else:
    st.warning("Nenhum dado mensal disponível.")

# Gráficos
if not weekly_historical.empty and 'Período' in weekly_historical.columns and 'EXPORTAÇÕES Valor' in weekly_historical.columns:
    st.subheader("Evolução das Exportações Semanais")
    st.line_chart(weekly_historical.set_index('Período')[['EXPORTAÇÕES Valor']].rename(columns={'EXPORTAÇÕES Valor': 'Exportações (US$)'}))

if not monthly_historical.empty and 'Mês' in monthly_historical.columns and 'EXPORTAÇÕES Valor' in monthly_historical.columns:
    st.subheader("Evolução das Exportações Mensais")
    st.line_chart(monthly_historical.set_index('Mês')[['EXPORTAÇÕES Valor']].rename(columns={'EXPORTAÇÕES Valor': 'Exportações (US$)'}))
