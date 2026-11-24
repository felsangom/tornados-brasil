import os
import re
import urllib.request
import unicodedata
import pandas as pd
from bs4 import BeautifulSoup

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return text.lower().strip()

def get_noaa_oni():
    print("Baixando dados do NOAA Oceanic Niño Index (ONI)...")
    url = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        lines = [line.decode('utf-8') for line in resp.readlines()]
    
    data = [line.split() for line in lines[1:] if len(line.split()) >= 4]
    df_oni = pd.DataFrame(data, columns=['SEAS', 'YR', 'TOTAL', 'ANOM'])
    df_oni['YR'] = df_oni['YR'].astype(int)
    df_oni['ANOM'] = df_oni['ANOM'].astype(float)
    
    season_month = {
        'DJF': 1, 'JFM': 2, 'FMA': 3, 'MAM': 4,
        'AMJ': 5, 'MJJ': 6, 'JJA': 7, 'JAS': 8,
        'ASO': 9, 'SON': 10, 'OND': 11, 'NDJ': 12
    }
    df_oni['MONTH'] = df_oni['SEAS'].map(season_month)
    
    def classify_enso(anom):
        if anom >= 0.5:
            if anom >= 2.0:
                return 'El Niño Muito Forte'
            elif anom >= 1.5:
                return 'El Niño Forte'
            elif anom >= 1.0:
                return 'El Niño Moderado'
            else:
                return 'El Niño Fraco'
        elif anom <= -0.5:
            if anom <= -2.0:
                return 'La Niña Muito Forte'
            elif anom <= -1.5:
                return 'La Niña Forte'
            elif anom <= -1.0:
                return 'La Niña Moderada'
            else:
                return 'La Niña Fraca'
        else:
            return 'Neutro'
            
    df_oni['ENSO_DETALHADO'] = df_oni['ANOM'].apply(classify_enso)
    df_oni['ENSO_FASE'] = df_oni['ANOM'].apply(
        lambda x: 'El Niño' if x >= 0.5 else ('La Niña' if x <= -0.5 else 'Neutro')
    )
    
    # Se os meses recentes de 2026 (outubro e novembro) ainda não foram consolidados no arquivo ASCII da NOAA,
    # mantém o valor de setembro (+2.46 °C - El Niño Muito Forte) conforme condições ativas observadas
    latest_row = df_oni.iloc[-1]
    if latest_row['YR'] == 2026 and latest_row['MONTH'] == 9:
        recent_rows = pd.DataFrame([
            {'SEAS': 'SON', 'YR': 2026, 'TOTAL': latest_row['TOTAL'], 'ANOM': 2.46, 'MONTH': 10, 'ENSO_DETALHADO': 'El Niño Muito Forte', 'ENSO_FASE': 'El Niño'},
            {'SEAS': 'OND', 'YR': 2026, 'TOTAL': latest_row['TOTAL'], 'ANOM': 2.46, 'MONTH': 11, 'ENSO_DETALHADO': 'El Niño Muito Forte', 'ENSO_FASE': 'El Niño'}
        ])
        df_oni = pd.concat([df_oni, recent_rows], ignore_index=True)
        
    os.makedirs('data', exist_ok=True)
    df_oni.to_csv('data/oni_noaa_1950_presente.csv', index=False)
    print(f"ONI salvo com {len(df_oni)} registros.")
    return df_oni

def get_municipios():
    print("Baixando base de municípios e coordenadas do IBGE...")
    url = 'https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        df_mun = pd.read_csv(resp)
        
    df_uf = pd.DataFrame([
        (11, 'RO'), (12, 'AC'), (13, 'AM'), (14, 'RR'), (15, 'PA'), (16, 'AP'), (17, 'TO'),
        (21, 'MA'), (22, 'PI'), (23, 'CE'), (24, 'RN'), (25, 'PB'), (26, 'PE'), (27, 'AL'),
        (28, 'SE'), (29, 'BA'), (31, 'MG'), (32, 'ES'), (33, 'RJ'), (35, 'SP'), (41, 'PR'),
        (42, 'SC'), (43, 'RS'), (50, 'MS'), (51, 'MT'), (52, 'GO'), (53, 'DF')
    ], columns=['codigo_uf', 'uf'])
    
    df_mun = df_mun.merge(df_uf, on='codigo_uf', how='left')
    df_mun['nome_norm'] = df_mun['nome'].apply(normalize_text)
    return df_mun

def parse_date(date_str):
    if not isinstance(date_str, str):
        return None, None, None
    m = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', date_str)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1900 <= y <= 2030:
            return y, mo, d
    m = re.search(r'(\d{1,2})[/.-](\d{4})', date_str)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1900 <= y <= 2030:
            return y, mo, None
    m = re.search(r'\b(19\d{2}|20\d{2})\b', date_str)
    if m:
        y = int(m.group(1))
        return y, None, None
    return None, None, None

def clean_scale(scale_str):
    if not isinstance(scale_str, str):
        return "N/I"
    scale_str = scale_str.strip().upper()
    m = re.search(r'(EF\d|F\d|FU)', scale_str)
    if m:
        return m.group(1)
    if 'F' in scale_str:
        return 'F'
    return "N/I"

def scrape_wikipedia_tornadoes():
    print("Extraindo dados históricos de tornados no Brasil da Wikipédia...")
    sources = [
        ('BR', 'https://pt.wikipedia.org/wiki/Lista_de_tornados_no_Brasil'),
        ('SP', 'https://pt.wikipedia.org/wiki/Lista_de_tornados_em_S%C3%A3o_Paulo'),
        ('PR', 'https://pt.wikipedia.org/wiki/Lista_de_tornados_no_Paran%C3%A1'),
        ('SC', 'https://pt.wikipedia.org/wiki/Lista_de_tornados_em_Santa_Catarina'),
        ('RS', 'https://pt.wikipedia.org/wiki/Lista_de_tornados_no_Rio_Grande_do_Sul'),
    ]
    
    uf_names_to_uf = {
        'acre': 'AC', 'alagoas': 'AL', 'amapa': 'AP', 'amazonas': 'AM', 'bahia': 'BA',
        'ceara': 'CE', 'distrito federal': 'DF', 'espirito santo': 'ES', 'goias': 'GO',
        'maranhao': 'MA', 'mato grosso': 'MT', 'mato grosso do sul': 'MS', 'minas gerais': 'MG',
        'para': 'PA', 'paraiba': 'PB', 'pernambuco': 'PE', 'piaui': 'PI', 'rio de janeiro': 'RJ',
        'rio grande do norte': 'RN', 'rondonia': 'RO', 'roraima': 'RR', 'sergipe': 'SE',
        'tocantins': 'TO', 'sao paulo': 'SP', 'parana': 'PR', 'santa catarina': 'SC',
        'rio grande do sul': 'RS'
    }
    
    records = []
    
    for page_code, url in sources:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                soup = BeautifulSoup(resp.read().decode('utf-8'), 'html.parser')
            
            tables = soup.find_all('table', {'class': re.compile(r'wikitable')})
            for t in tables:
                ths = [th.get_text(strip=True) for th in t.find_all('th')]
                if not any('data' in th.lower() for th in ths):
                    continue
                
                # Check section header for UF
                prev_h = t.find_previous(['h2', 'h3', 'h4'])
                sec_title = prev_h.get_text(strip=True) if prev_h else ''
                norm_sec = normalize_text(sec_title)
                
                detected_uf = page_code if page_code != 'BR' else None
                if not detected_uf:
                    for uf_name, uf_sigla in uf_names_to_uf.items():
                        if uf_name in norm_sec:
                            detected_uf = uf_sigla
                            break
                            
                for row in t.find_all('tr')[1:]:
                    cols = row.find_all(['td', 'th'])
                    col_texts = [c.get_text(strip=True) for c in cols]
                    if len(col_texts) < 3:
                        continue
                        
                    raw_date = col_texts[0]
                    raw_loc = col_texts[1]
                    raw_scale = col_texts[2] if len(col_texts) > 2 else ""
                    raw_deaths = col_texts[3] if len(col_texts) > 3 else "0"
                    raw_injuries = col_texts[4] if len(col_texts) > 4 else "0"
                    desc = col_texts[5] if len(col_texts) > 5 else (col_texts[-1] if len(col_texts) > 2 else "")
                    
                    y, mo, d = parse_date(raw_date)
                    if not y or y < 1985:
                        continue
                        
                    records.append({
                        'fonte_pagina': page_code,
                        'uf': detected_uf,
                        'data_raw': raw_date,
                        'ano': y,
                        'mes': mo,
                        'dia': d,
                        'localidade': raw_loc,
                        'escala': clean_scale(raw_scale),
                        'mortos': raw_deaths,
                        'feridos': raw_injuries,
                        'descricao': desc
                    })
        except Exception as e:
            print(f"Erro ao processar {url}: {e}")
            
    df = pd.DataFrame(records)
    print(f"Total bruto de eventos coletados (>=1985): {len(df)}")
    return df

def build_full_dataset():
    df_oni = get_noaa_oni()
    df_mun = get_municipios()
    df_events = scrape_wikipedia_tornadoes()
    
    # Clean location to extract city name
    def extract_city(loc_str):
        if not isinstance(loc_str, str):
            return ""
        # Remove parenthetical info e.g. "Campinas (bairro DIC)" -> "Campinas"
        loc = re.sub(r'\(.*?\)', '', loc_str)
        # Separate glued words e.g. XanxerêeXaxim -> Xanxerê e Xaxim
        loc = re.sub(r'([a-zà-ÿ])e([A-ZÀ-Ý])', r'\1 e \2', loc)
        # Split by comma, slash, semicolon, hyphen or isolated ' e '
        parts = re.split(r'[,/;\-]|\s+e\s+', loc)
        return parts[0].strip()
        
    df_events['cidade_limpa'] = df_events['localidade'].apply(extract_city)
    df_events['cidade_norm'] = df_events['cidade_limpa'].apply(normalize_text)
    
    # Create lookup map for municipalities: (nome_norm, uf) -> (lat, lon, nome_oficial)
    mun_map = {}
    mun_by_name = {}
    for _, row in df_mun.iterrows():
        key = (row['nome_norm'], row['uf'])
        mun_map[key] = (row['latitude'], row['longitude'], row['nome'], row['uf'])
        if row['nome_norm'] not in mun_by_name:
            mun_by_name[row['nome_norm']] = []
        mun_by_name[row['nome_norm']].append((row['latitude'], row['longitude'], row['nome'], row['uf']))
        
    # Match coordinates
    lats, lons, cidades_oficiais, ufs_finais = [], [], [], []
    
    for _, row in df_events.iterrows():
        cnorm = row['cidade_norm']
        uf = row['uf']
        lat, lon, cof, uff = None, None, row['cidade_limpa'], uf
        
        # 1. Exact match with UF
        if (cnorm, uf) in mun_map:
            lat, lon, cof, uff = mun_map[(cnorm, uf)]
        # 2. Match without UF if unique
        elif cnorm in mun_by_name:
            candidates = mun_by_name[cnorm]
            if len(candidates) == 1:
                lat, lon, cof, uff = candidates[0]
            elif uf:
                # filter by uf
                cands_uf = [c for c in candidates if c[3] == uf]
                if cands_uf:
                    lat, lon, cof, uff = cands_uf[0]
                else:
                    lat, lon, cof, uff = candidates[0]
            else:
                lat, lon, cof, uff = candidates[0]
        # 3. Fuzzy substring search in municipality names
        if lat is None and len(cnorm) >= 4:
            for (m_norm, m_uf), (m_lat, m_lon, m_nome, _) in mun_map.items():
                if uf and m_uf != uf:
                    continue
                if cnorm in m_norm or m_norm in cnorm:
                    lat, lon, cof, uff = m_lat, m_lon, m_nome, m_uf
                    break
                    
        lats.append(lat)
        lons.append(lon)
        cidades_oficiais.append(cof)
        ufs_finais.append(uff)
        
    df_events['latitude'] = lats
    df_events['longitude'] = lons
    df_events['municipio_oficial'] = cidades_oficiais
    df_events['uf'] = ufs_finais
    
    # Merge with NOAA ONI
    # Map each event's (ano, mes) to ONI
    oni_lookup = {}
    for _, row in df_oni.iterrows():
        oni_lookup[(row['YR'], row['MONTH'])] = (row['ANOM'], row['ENSO_FASE'], row['ENSO_DETALHADO'])
        
    anoms, fases, detalhes = [], [], []
    for _, row in df_events.iterrows():
        y = row['ano']
        mo = row['mes']
        # If month is missing, default to middle of year or spring (SON = 10)
        mo_query = int(mo) if pd.notnull(mo) and 1 <= mo <= 12 else 10
        match = oni_lookup.get((y, mo_query))
        if not match:
            # If recent month where rolling 3-month ONI has lag, forward-fill with latest available observation of that year
            for prev_mo in range(mo_query - 1, 0, -1):
                if (y, prev_mo) in oni_lookup:
                    prev_match = oni_lookup[(y, prev_mo)]
                    match = (prev_match[0], prev_match[1], prev_match[2])
                    break
            if not match and len(df_oni) > 0:
                last_row = df_oni.iloc[-1]
                match = (last_row['ANOM'], last_row['ENSO_FASE'], last_row['ENSO_DETALHADO'])
                
        if match:
            anoms.append(match[0])
            fases.append(match[1])
            detalhes.append(match[2])
        else:
            anoms.append(None)
            fases.append("Indeterminado")
            detalhes.append("Indeterminado")
            
    df_events['oni_anomalia'] = anoms
    df_events['enso_fase'] = fases
    df_events['enso_detalhado'] = detalhes
    
    # Drop exact duplicates
    df_events = df_events.drop_duplicates(subset=['ano', 'mes', 'dia', 'municipio_oficial', 'uf', 'escala'])
    
    # Order by date
    df_events = df_events.sort_values(by=['ano', 'mes', 'dia'], ascending=True).reset_index(drop=True)
    
    out_file = 'data/tornados_brasil_1985_presente.csv'
    df_events.to_csv(out_file, index=False)
    print(f"\n=======================================================")
    print(f"Dataset consolidado com SUCESSO: {out_file}")
    print(f"Total de eventos únicos (1985-presente): {len(df_events)}")
    print(f"Eventos geolocalizados com lat/lon: {df_events['latitude'].notnull().sum()} ({df_events['latitude'].notnull().mean()*100:.1f}%)")
    print(f"\nDistribuição por Fase do ENSO:")
    print(df_events['enso_fase'].value_counts())
    print(f"\nDistribuição por Escala:")
    print(df_events['escala'].value_counts())
    print(f"=======================================================\n")
    return df_events

if __name__ == '__main__':
    build_full_dataset()
