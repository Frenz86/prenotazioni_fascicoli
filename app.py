import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from PIL import Image
from typing import Tuple, Dict
from dataclasses import dataclass
import time

st.set_page_config(
                    page_title="FBS - Richieste Fascicoli",
                    page_icon=Image.open("img/FBS.jpg"),
                    )

st.markdown("""
            <style>
            .required {
                color: red !important;
                font-size: 0.8em;
                margin-top: 0.2em;
            }
            </style>
            """, unsafe_allow_html=True)

@dataclass
class Config:
    REQUIRED_COLUMNS = [
                        'PORTAFOGLIO', 'NDG', 'DATA_RICHIESTA','PRENOTATO', 'RESTITUITO', 'DATA_EVASIONE', 'DATA_RESTITUZIONE',
                        'GESTORE','MOTIVAZIONE_RICHIESTA','NOTE', 'MOTIVO_SINGOLO_DOC','INDIC_DOC_SCANSIONARE','DETTAGLIO_RICHIESTA_INTERO',
                        ]
    MOTIVAZIONI = [
                    "Scansione intero fascicolo (solo se completamente assente o privo di documentazione rilevante)",
                    #"Richiesta fascicolo cartaceo per scansione singolo documento  (compilare campo dettaglio scansione) solo per escussione garanzia consortile, richiesta specifica debitori, reclami",
                    "Richiesta fascicolo CARTACEO",
                    ]
    
    BOOL_COLUMNS = ['PRENOTATO', 'RESTITUITO']

    #UNICA
    MOTIVAZIONE_SCANSIONE_SINGOLO_DOC = ["Escussione garanzia consortile",
                                        "Richiesta documentale dai debitori",
                                        "Reclami",
                                        "Azionare il credito ",
                                        "Verifica atti interruttivi prescrizione ( solo auotorizzato da TL )",
                                        ]              
    #MULTIPLA
    INDICARE_DOCUMENTO_DA_SCANSIONARE = ["Atti interruttivi della prescrizione solo per azionare il credito / reclamo. Per altre motivazioni valuteremo internamento l' evasione",
                                        "Contratto di conto corrente",
                                        "Contratto Mutuo chirografario",
                                        "Contratto Mutuo Ipotecario",
                                        "Fideiussioni",
                                        "Atti legali Vari",
                                        "Garanzie consortili",
                                        "Lettera di messa in mora",
                                        "Altro ( specificare campo note )",
                                        ]
    #UNICA
    DETTAGLIO_RICHIESTA_INTERO_FASCICOLO_CARTACEO = ["Azionare il credito ( necessario titolo / doc in originale )",
                                                        ]

def render_search_filters(df: pd.DataFrame) -> Tuple[str, str, str, pd.DataFrame]:
    st.sidebar.header("Filtri di Ricerca")
    
    portafogli_list = sorted(df['PORTAFOGLIO'].unique())
    portafoglio = st.sidebar.selectbox(
                                        "Seleziona Portafoglio *",
                                        options=[''] + portafogli_list,
                                        index=0
                                        )
    if not portafoglio:
        st.sidebar.markdown('<p class="required">⚠️ La selezione del Portafoglio è obbligatoria</p>', 
                          unsafe_allow_html=True)
    
    ndg_list = sorted(df['NDG'].unique().astype(str)) if not portafoglio else \
               sorted(df[df['PORTAFOGLIO'] == portafoglio]['NDG'].unique().astype(str))
    ndg = st.sidebar.selectbox(
                                "Seleziona NDG *",
                                options=[''] + ndg_list,
                                index=0
                                )
    if not ndg:
        st.sidebar.markdown('<p class="required">⚠️ La selezione del NDG è obbligatoria</p>', 
                          unsafe_allow_html=True)
    
    motivazione = st.sidebar.selectbox(
                                        "Motivazione Richiesta *",
                                        options=[''] + Config.MOTIVAZIONI,
                                        index=0,
                                        key="motivazione_selectbox"
                                        )
    if not motivazione:
        st.sidebar.markdown('<p class="required">⚠️ La selezione della Motivazione è obbligatoria</p>', 
                          unsafe_allow_html=True)
    
    return portafoglio, ndg, motivazione

def render_booking_form(gestori: pd.DataFrame) -> str:
    st.markdown("### Informazioni Richiedente")
    st.markdown("I campi contrassegnati con * sono obbligatori")
    
    cols = st.columns(2)
    with cols[0]:
        gestore_list = sorted(gestori['NOME_VIS'].unique())
        gestore = st.selectbox(
                                "Seleziona Gestore *",
                                options=[''] + gestore_list,
                                index=0
                                )   
        if not gestore:
            st.markdown('<p class="required">Il Gestore è obbligatorio</p>', 
                      unsafe_allow_html=True)
    
    return gestore

# --- FUNZIONE DI AUTENTICAZIONE OTTIMIZZATA ---
@st.cache_resource
def get_gspread_client() -> gspread.Client:
    """
    Si connette a Google Sheets usando le credenziali di Streamlit Secrets
    e mette in cache la connessione per riutilizzarla.
    """
    try:
        credentials = {
            "type": st.secrets["type"],
            "project_id": st.secrets["project_id"],
            "private_key_id": st.secrets["private_key_id"],
            "private_key": st.secrets["private_key"],
            "client_email": st.secrets["client_email"],
            "client_id": st.secrets["client_id"],
            "auth_uri": st.secrets["auth_uri"],
            "token_uri": st.secrets["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["client_x509_cert_url"]
        }
        return gspread.service_account_from_dict(credentials)
    except Exception as e:
        st.error(f"Errore durante l'autenticazione a Google Sheets: {e}")
        raise


def force_remove_all_filters(worksheet):
    """
    Rimuove TUTTI i tipi di filtri usando le API Google Sheets
    """
    try:
        spreadsheet = worksheet.spreadsheet
        sheet_id = worksheet.id
        
        # Get current sheet metadata to see what filters exist
        sheet_metadata = spreadsheet.fetch_sheet_metadata()
        
        requests = []
        
        # Find our specific sheet
        target_sheet = None
        for sheet in sheet_metadata['sheets']:
            if sheet['properties']['sheetId'] == sheet_id:
                target_sheet = sheet
                break
        
        if target_sheet:
            # Remove basic filter if it exists
            if 'basicFilter' in target_sheet:
                requests.append({
                    "clearBasicFilter": {
                        "sheetId": sheet_id
                    }
                })
            
            # Remove all filter views if they exist
            if 'filterViews' in target_sheet:
                for filter_view in target_sheet['filterViews']:
                    requests.append({
                        "deleteFilterView": {
                            "filterId": filter_view['filterViewId']
                        }
                    })
        
        # Also try to clear any basic filter that might not be in metadata
        requests.append({
            "clearBasicFilter": {
                "sheetId": sheet_id
            }
        })
        
        # Execute all requests
        if requests:
            spreadsheet.batch_update({"requests": requests})
            
        # Double-check: try the gspread method too
        try:
            worksheet.clear_basic_filter()
        except:
            pass
            
    except Exception as e:
        print(f"Warning: Could not remove all filters: {e}")

# --- FUNZIONE PER CARICARE I DATI ---
@st.cache_data(ttl=60)
def load_google_sheets_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Carica i dati dai fogli Google specificati in DataFrame Pandas.
    Usa la cache di Streamlit per evitare ricaricamenti frequenti.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(st.secrets["gsheet_id"])
        
        worksheets = {
            "database": sh.worksheet("database"),
            "prenotazioni": sh.worksheet("prenotazioni"),
            "gestori": sh.worksheet("gestori"),
        }
        
        # RIMUOVI TUTTI I FILTRI PRIMA DI LEGGERE
        for name, ws in worksheets.items():
            force_remove_all_filters(ws)
        
        dfs = {name: pd.DataFrame(ws.get_all_records()) for name, ws in worksheets.items()}
        
        # Usa la configurazione dalla classe Config
        for col in Config.BOOL_COLUMNS:
            if col in dfs['prenotazioni'].columns:
                dfs['prenotazioni'][col] = dfs['prenotazioni'][col].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '': False}).fillna(False)
        
        return dfs['database'], dfs['prenotazioni'], dfs['gestori']
    
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati da Google Sheets: {e}")
        raise


# --- FUNZIONE PER SALVARE UNA NUOVA PRENOTAZIONE ---
def save_prenotazione(prenotazioni: pd.DataFrame, new_prenotazione: Dict) -> pd.DataFrame:
    """
    Salva una nuova riga di prenotazione nel foglio Google e aggiorna il DataFrame locale.
    Usa get_all_values() per calcolare l'ultima riga effettiva, ignorando i filtri.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(st.secrets["gsheet_id"])
        prenotazioni_w = sh.worksheet("prenotazioni")

        # RIMUOVI TUTTI I FILTRI PRIMA DI SALVARE
        force_remove_all_filters(prenotazioni_w)

        # --- METODO ALTERNATIVO: CALCOLA L'ULTIMA RIGA CON get_all_values() ---
        # Questo metodo legge TUTTI i dati reali del foglio, ignorando completamente i filtri
        all_values = prenotazioni_w.get_all_values()
        next_row = len(all_values) + 1  # La prossima riga disponibile
        
        # Preparazione dei dati per la scrittura
        if 'DATA_RICHIESTA' in new_prenotazione and new_prenotazione['DATA_RICHIESTA']:
            if not isinstance(new_prenotazione['DATA_RICHIESTA'], (datetime, pd.Timestamp)):
                new_prenotazione['DATA_RICHIESTA'] = pd.to_datetime(new_prenotazione['DATA_RICHIESTA'])
            
            new_prenotazione['DATA_RICHIESTA'] = new_prenotazione['DATA_RICHIESTA'].strftime('%d/%m/%Y')

        # Usa la configurazione dalla classe Config per le colonne booleane
        for key in Config.BOOL_COLUMNS:
            if key in new_prenotazione:
                new_prenotazione[key] = str(new_prenotazione[key]).upper()

        # Usa la configurazione dalla classe Config per l'ordine delle colonne
        new_row_data = [str(new_prenotazione.get(col, '')) for col in Config.REQUIRED_COLUMNS]
        
        # Inserisce direttamente nella riga calcolata usando update() invece di append_row()
        end_col = chr(ord('A') + len(Config.REQUIRED_COLUMNS) - 1)
        range_name = f"A{next_row}:{end_col}{next_row}"
        prenotazioni_w.update(range_name, [new_row_data], value_input_option="USER_ENTERED")

        # Aggiorna il DataFrame locale per riflettere immediatamente la modifica nell'UI
        new_df = pd.DataFrame([new_prenotazione])
        updated_prenotazioni = pd.concat([prenotazioni, new_df], ignore_index=True)
        
        updated_prenotazioni['DATA_RICHIESTA'] = pd.to_datetime(updated_prenotazioni['DATA_RICHIESTA'], format='%d/%m/%Y', errors='coerce')
        updated_prenotazioni = updated_prenotazioni.sort_values(by='DATA_RICHIESTA', ascending=True, ignore_index=True)
        
        st.success("Prenotazione salvata con successo!")
        load_google_sheets_data.clear()
        
        return updated_prenotazioni
        
    except Exception as e:
        st.error(f"Errore critico durante il salvataggio della prenotazione: {e}")
        raise

def render_login_page():
    st.title('Login Richieste Fascicoli')
    try:
        logo = Image.open('img/FBS.jpg')
        st.image(logo, width=600)
    except Exception:
        st.warning("Logo non trovato")
    
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    
    if st.button('Login', type="primary"):
        if username == st.secrets["USER"] and password == st.secrets["PASSW"]:
            st.session_state.user_state.update({
                'username': username,
                'password': password,
                'logged_in': True
            })
            st.success('Login effettuato con successo')
            st.rerun()
        else:
            st.error('Username o password non validi')

def init_session_state():
    if 'user_state' not in st.session_state:
        st.session_state.user_state = {
                                        'username': '',
                                        'password': '',
                                        'logged_in': False
                                        }
    if 'search_clicked' not in st.session_state:
        st.session_state.search_clicked = False
    if 'last_data_load' not in st.session_state:
        st.session_state.last_data_load = 0

def render_result_card(row: pd.Series):
    st.markdown(f"""
        <div style='color: #87CEEB'>
            <h5>Portafoglio: {row['PORTAFOGLIO']} - NDG: {row['NDG']} - Nominativo: {row['NOMINATIVO']}</h5>
            <h5>Codice Scatola: {row['SCATOLA']} - CREDITLINE: {row['ID_CREDITLINE_ACERO']} </h5>
        </div>
    """, unsafe_allow_html=True)

def main():
    init_session_state()

    if not st.session_state.user_state['logged_in']:
        render_login_page()
        return
    
    st.title("Richieste Fascicoli FBS")    

    if st.sidebar.button("🔄 Ricarica Dati"):
        load_google_sheets_data.clear()
        st.session_state.last_data_load = time.time()
        st.rerun()
    
    # Force refresh data if it's been more than 10 seconds
    current_time = time.time()
    if current_time - st.session_state.last_data_load > 10:
        load_google_sheets_data.clear()
        st.session_state.last_data_load = current_time
    
    try:
        database, prenotazioni, gestori = load_google_sheets_data()
    except Exception:
        return
    
    # Create debug expander to view current data
    with st.sidebar.expander("Debug Info", expanded=False):
        st.write(f"Data last refreshed: {st.session_state.last_data_load}")
        st.write(f"Total prenotations: {len(prenotazioni)}")
        st.write(f"Non-returned prenotations: {len(prenotazioni[~prenotazioni['RESTITUITO']])}")
    
    df = database.copy()
    df['DISPONIBILE'] = True
    
    # Get fresh active prenotations
    active_prenotations = prenotazioni[~prenotazioni['RESTITUITO']].copy()
    
    # Generate check_keys for all active prenotations
    if not active_prenotations.empty:
        active_prenotations['check_key'] = active_prenotations.apply(
            lambda x: f"{str(x['NDG'])}_{str(x['PORTAFOGLIO'])}_{str(x['MOTIVAZIONE_RICHIESTA'])}", 
            axis=1
        )
        
        # Debug check keys
        with st.sidebar.expander("Active Prenotations", expanded=False):
            st.write(active_prenotations[['NDG', 'PORTAFOGLIO', 'MOTIVAZIONE_RICHIESTA', 'check_key']])
    
    portafoglio, ndg, motivazione = render_search_filters(df)
    
    if st.sidebar.button("Cerca"):
        if not ndg:
            st.sidebar.error("Devi selezionare un NDG prima di cercare")
            return
        
        # Force reload data to ensure we have the latest prenotations
        load_google_sheets_data.clear()
        database, prenotazioni, gestori = load_google_sheets_data()
        active_prenotations = prenotazioni[~prenotazioni['RESTITUITO']].copy()
        
        if not active_prenotations.empty:
            active_prenotations['check_key'] = active_prenotations.apply(
                lambda x: f"{str(x['NDG'])}_{str(x['PORTAFOGLIO'])}_{str(x['MOTIVAZIONE_RICHIESTA'])}", 
                axis=1
            )
        
        st.session_state.search_clicked = True
    
    if st.session_state.search_clicked and ndg:
        mask = (df['NDG'].astype(str) == ndg)
        if portafoglio:
            mask &= (df['PORTAFOGLIO'] == portafoglio)
        risultati = df[mask]
        
        if risultati.empty:
            st.warning("Nessun risultato trovato per i criteri di ricerca specificati")
            return
        
        # Check if a prenotation already exists
        if motivazione and not active_prenotations.empty:
            check_key = f"{str(ndg)}_{str(portafoglio)}_{str(motivazione)}"
            st.write("Current check key:", check_key)  # Debug line
            
            if check_key in active_prenotations['check_key'].values:
                st.warning(f"Esiste già una prenotazione attiva per questo NDG/Portafoglio con la motivazione: {motivazione}")
                return
        
        for _, row in risultati.iterrows():
            render_result_card(row)
        gestore = render_booking_form(gestori)

        ###################################################################################

        notes = "-"
        mot_singolo_doc = "-"
        indic_doc_scansionare = "-"
        dettaglio_richiesta_intero = "-"
        if motivazione in ["Scansione intero fascicolo (solo se completamente assente o privo di documentazione rilevante)"]:
            st.markdown("")
            notes = st.text_area("Note aggiuntive", key="note")
        ##ok
        ##### modifica Valentina #########################################################
        
        indic_doc_scansionare = "-"
        dettaglio_richiesta_intero = "-"
        if motivazione in ["Richiesta fascicolo CARTACEO"]:
            tipologia_cartaceo = st.radio("Selezionare l'opzione",
                                    options=["SINGOLO", "COMPLETO"],  # Add this line
                                    captions=[
                                        "SINGOLO",
                                        "COMPLETO",
                                    ],
                                )

            if tipologia_cartaceo == "SINGOLO":
                st.markdown("")
                xx = "specificare IL NUMERO DI FASCILO e la motivazione soprattutto per escussione garanzia consortile, richiesta specifica debitori, reclami"
                notes = st.text_area(xx, key="note")
                mot_singolo_doc = "FASCICOLO SINGOLO"
            else:
                xx = "specificare la motivazione soprattutto per escussione garanzia consortile, richiesta specifica debitori, reclami"
                notes = st.text_area(xx, key="note")
                mot_singolo_doc = "FASCICOLO COMPLETO"

        if st.button("Prenota Fascicolo"):
            if not all([ndg, motivazione, gestore]):
                st.error("Tutti i campi obbligatori devono essere compilati")
                return

            # Force data reload before saving to ensure we have latest data
            load_google_sheets_data.clear()
            database, prenotazioni, gestori = load_google_sheets_data()
            
            ndg_riga = risultati.iloc[0]['NDG']
            portafoglio_riga = risultati.iloc[0]['PORTAFOGLIO']

            new_prenotazione = {
                                'NDG': ndg_riga,
                                'PORTAFOGLIO': portafoglio_riga,
                                'DATA_RICHIESTA': datetime.now().strftime('%d/%m/%Y'),
                                'MOTIVAZIONE_RICHIESTA': motivazione,
                                'PRENOTATO': True,
                                'RESTITUITO': False,
                                'DATA_EVASIONE': '',
                                'DATA_RESTITUZIONE': '',
                                'GESTORE': gestore,
                                'MOTIVO_SINGOLO_DOC': mot_singolo_doc,
                                'INDIC_DOC_SCANSIONARE': indic_doc_scansionare,
                                'DETTAGLIO_RICHIESTA_INTERO':dettaglio_richiesta_intero,
                                'NOTE': notes,
                                }
            
            save_prenotazione(prenotazioni, new_prenotazione)
            st.success("Fascicolo prenotato con successo!")
            st.session_state.search_clicked = False
            st.rerun()
                
    st.sidebar.markdown("---")
    st.sidebar.subheader("Informazioni Database")
    st.sidebar.info(f"""
                    - Portafogli disponibili: {len(df['PORTAFOGLIO'].unique())}
                    - Totale fascicoli: {len(df)}
                    """)

if __name__ == "__main__":
    main()