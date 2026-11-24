import pandas as pd
import folium
from folium.plugins import MarkerCluster, FeatureGroupSubGroup

def build_interactive_map():
    csv_path = 'data/tornados_brasil_1985_presente.csv'
    df = pd.read_csv(csv_path)
    
    # Filter only events with valid coordinates
    df_geo = df[df['latitude'].notnull() & df['longitude'].notnull()].copy()
    print(f"Gerando mapa interativo para {len(df_geo)} eventos geolocalizados...")
    
    m = folium.Map(
        location=[-24.0, -51.0],
        zoom_start=5,
        tiles=None,
        control_scale=True
    )
    
    # Camada base confiável da Esri (sem bloqueio de política de tiles)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri &mdash; StreetMap',
        name='Mapa de Ruas (Esri)'
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri &mdash; Topográfico',
        name='Topográfico (Esri)'
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        attr='Esri &mdash; Cinza Claro',
        name='Fundo Claro / Minimalista (Esri)'
    ).add_to(m)
    
    # Main parent cluster
    parent_cluster = MarkerCluster(name="Agrupamento Geral", options={'maxClusterRadius': 40}).add_to(m)
    
    # Subgroups for layer control
    group_nino = FeatureGroupSubGroup(parent_cluster, '🔥 El Niño (Águas quentes no Pacífico)')
    group_nina = FeatureGroupSubGroup(parent_cluster, '❄️ La Niña (Águas frias no Pacífico)')
    group_neutro = FeatureGroupSubGroup(parent_cluster, '⚪ Fase Neutra')
    
    # Colors and styles
    color_map = {
        'El Niño': '#d9381e',    # Red/Warm
        'La Niña': '#1e6fd9',    # Blue/Cold
        'Neutro': '#555555'      # Neutral Dark Gray
    }
    
    for _, row in df_geo.iterrows():
        fase = row['enso_fase'] if row['enso_fase'] in color_map else 'Neutro'
        color = color_map.get(fase, '#555555')
        
        # Determine target group
        if fase == 'El Niño':
            target_group = group_nino
        elif fase == 'La Niña':
            target_group = group_nina
        else:
            target_group = group_neutro
            
        cidade = row['municipio_oficial'] if pd.notnull(row['municipio_oficial']) else row['localidade']
        uf = row['uf'] if pd.notnull(row['uf']) else ''
        escala = row['escala'] if pd.notnull(row['escala']) else 'N/I'
        data_str = row['data_raw']
        anom = f"{row['oni_anomalia']:+.2f} °C" if pd.notnull(row['oni_anomalia']) else "N/D"
        detalhe_enso = row['enso_detalhado'] if pd.notnull(row['enso_detalhado']) else fase
        mortos = row['mortos'] if pd.notnull(row['mortos']) else "0"
        feridos = row['feridos'] if pd.notnull(row['feridos']) else "0"
        desc = row['descricao'] if pd.notnull(row['descricao']) and str(row['descricao']) != 'nan' else 'Sem descrição detalhada disponível.'
        
        # Truncate description if very long
        if len(desc) > 300:
            desc = desc[:297] + '...'
            
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 13px; width: 280px; line-height: 1.4;">
            <div style="background-color: {color}; color: white; padding: 6px 10px; border-radius: 4px; font-weight: bold; margin-bottom: 8px;">
                🌪️ Tornado {escala} - {cidade}/{uf}
            </div>
            <p style="margin: 3px 0;"><strong>Data:</strong> {data_str}</p>
            <p style="margin: 3px 0;"><strong>Fase ENSO:</strong> <span style="color: {color}; font-weight: bold;">{detalhe_enso}</span> (ONI: {anom})</p>
            <p style="margin: 3px 0;"><strong>Vítimas:</strong> {mortos} mortos | {feridos} feridos</p>
            <hr style="margin: 6px 0; border: 0; border-top: 1px solid #ccc;">
            <p style="margin: 4px 0; color: #444; font-size: 12px;"><strong>Relato:</strong> {desc}</p>
        </div>
        """
        
        # Circle marker size based on scale
        radius = 7
        if 'F3' in escala or 'EF3' in escala:
            radius = 11
        elif 'F2' in escala or 'EF2' in escala:
            radius = 9
        elif 'F4' in escala:
            radius = 13
            
        marker = folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=radius,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{cidade}/{uf} ({data_str}) - {escala} | {detalhe_enso}"
        )
        marker.add_to(target_group)
        
    group_nino.add_to(m)
    group_nina.add_to(m)
    group_neutro.add_to(m)
    
    # Add Layer Control
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Legend HTML
    legend_html = """
     <div style="
     position: fixed; 
     bottom: 30px; left: 30px; width: 230px; height: 165px; 
     background-color: white; border:2px solid #bbb; border-radius: 6px; z-index:9999; font-size:12px;
     padding: 10px; box-shadow: 2px 2px 6px rgba(0,0,0,0.3); font-family: Arial, sans-serif;
     ">
     <strong style="font-size: 13px;">Ocorrência e ENSO (1985-Hoje)</strong><br>
     <i style="background:#d9381e; width: 14px; height: 14px; display:inline-block; border-radius:50%; margin-right: 6px; vertical-align: middle;"></i> <strong>El Niño</strong> (Anomalia &ge; +0.5°C)<br>
     <i style="background:#1e6fd9; width: 14px; height: 14px; display:inline-block; border-radius:50%; margin-right: 6px; vertical-align: middle;"></i> <strong>La Niña</strong> (Anomalia &le; -0.5°C)<br>
     <i style="background:#555555; width: 14px; height: 14px; display:inline-block; border-radius:50%; margin-right: 6px; vertical-align: middle;"></i> <strong>Neutro</strong> (-0.5°C a +0.5°C)<br>
     <hr style="margin: 6px 0; border: 0; border-top: 1px solid #ddd;">
     <small style="color: #666;">Tamanho do ponto = intensidade (F0 a F4).<br>Clique no ponto para detalhes.</small>
     </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    output_html = 'mapa_tornados_brasil_enso.html'
    m.save(output_html)
    print(f"Mapa salvo com sucesso em: {output_html}")
    return output_html

if __name__ == '__main__':
    build_interactive_map()
