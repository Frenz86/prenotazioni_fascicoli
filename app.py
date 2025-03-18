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
                    "Richiesta fascicolo cartaceo per scansione singolo documento  (compilare campo dettaglio scansione) solo per escussione garanzia consortile, richiesta specifica debitori, reclami",
                    "Richiesta intero fascicolo CARTACEO (compilare campo dettaglio Richiesta)",
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


@st.cache_data(ttl=45)
def load_google_sheets_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_key(st.secrets["gsheet_id"])
        
        worksheets = {
                    "database": sh.worksheet("database"),
                    "prenotazioni": sh.worksheet("prenotazioni"),
                    "gestori": sh.worksheet("gestori"),
                    #"centri_costo": sh.worksheet("centri_costo")
                    }
        dfs = {name: pd.DataFrame(ws.get_all_records()) for name, ws in worksheets.items()}
        
        # Improved boolean conversion
        for col in Config.BOOL_COLUMNS:
            if col in dfs['prenotazioni'].columns:
                dfs['prenotazioni'][col] = dfs['prenotazioni'][col].astype(str).str.upper().map({'TRUE': True, 'FALSE': False})
        
        return dfs['database'], dfs['prenotazioni'], dfs['gestori']
    
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        raise

def save_prenotazione(prenotazioni: pd.DataFrame, new_prenotazione: Dict) -> pd.DataFrame:
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
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_key(st.secrets["gsheet_id"])
        prenotazioni_w = sh.worksheet("prenotazioni")


        if 'DATA_RICHIESTA' in new_prenotazione and new_prenotazione['DATA_RICHIESTA']:
            if not isinstance(new_prenotazione['DATA_RICHIESTA'], (datetime, pd.Timestamp)):
                new_prenotazione['DATA_RICHIESTA'] = pd.to_datetime(new_prenotazione['DATA_RICHIESTA'])
            if isinstance(new_prenotazione['DATA_RICHIESTA'], (datetime, pd.Timestamp)):
                new_prenotazione['DATA_RICHIESTA'] = new_prenotazione['DATA_RICHIESTA'].strftime('%d/%m/%Y')

        for key in Config.BOOL_COLUMNS:
            if key in new_prenotazione:
                new_prenotazione[key] = str(new_prenotazione[key]).upper()


        new_row = [str(new_prenotazione.get(col, '')) for col in Config.REQUIRED_COLUMNS]
        prenotazioni_w.append_row(new_row)
        total_rows = len(prenotazioni_w.get_all_values())

        if total_rows > 1:
            try:
                for row in range(2, total_rows + 1):
                    prenotazioni_w.format(f'C{row}', {'numberFormat': {'type': 'DATE', 'pattern': 'dd/mm/yyyy'}})
                print("Formattazione completata cella per cella")
            except Exception as e:
                print(f"Errore durante la formattazione: {str(e)}")
        
        new_df = pd.DataFrame([new_prenotazione])
        updated_prenotazioni = pd.concat([prenotazioni, new_df], ignore_index=True)
        # Sort the DataFrame by DATA_RICHIESTA in ascending order
        updated_prenotazioni['DATA_RICHIESTA'] = pd.to_datetime(updated_prenotazioni['DATA_RICHIESTA'], format='%d/%m/%Y')
        updated_prenotazioni = updated_prenotazioni.sort_values(by='DATA_RICHIESTA', ascending=True, ignore_index=True)
        
        # Clear cache to ensure fresh data load
        st.success("Prenotazione salvata, aggiornamento dati in corso...")
        load_google_sheets_data.clear()
        
        return updated_prenotazioni
    except Exception as e:
        st.error(f"Error saving reservation: {str(e)}")
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
    
        if motivazione in ["Richiesta fascicolo cartaceo per scansione singolo documento  (compilare campo dettaglio scansione) solo per escussione garanzia consortile, richiesta specifica debitori, reclami"]:
            st.markdown("")

            mot_singolo_doc = st.selectbox(
                                            "MOTIVAZIONE SCANSIONE DEL SINGOLO DOCUMENTO *",
                                            options=[''] + Config.MOTIVAZIONE_SCANSIONE_SINGOLO_DOC,
                                            key="motivazione_scansione"
                                            )
            if not mot_singolo_doc:
                st.markdown('<p class="required">La motivazione è obbligatoria</p>', 
                            unsafe_allow_html=True)

            indic_doc_scansionare = st.multiselect(
                                                "INDICARE DOCUMENTO DA SCANSIONARE *",
                                                options=Config.INDICARE_DOCUMENTO_DA_SCANSIONARE,
                                                key="indic_doc_scansionare"
                                                )
            if not indic_doc_scansionare:
                st.markdown('<p class="required">Selezione il documento </p>', 
                            unsafe_allow_html=True)
            notes = st.text_area("Note aggiuntive", key="note")

        if motivazione in ["Richiesta intero fascicolo CARTACEO (compilare campo dettaglio Richiesta)"]:
            st.markdown("")
            dettaglio_richiesta_intero = st.selectbox(
                                                    "DETTAGLIO RICHIESTA INTERO FASCICOLO_CARTACEO *",
                                                    options=[''] + Config.DETTAGLIO_RICHIESTA_INTERO_FASCICOLO_CARTACEO,
                                                    key="dettaglio_richiesta_intero"
                                                    )
            if not dettaglio_richiesta_intero:
                st.markdown('<p class="required">Dettaglio Intero Fascicolo </p>', 
                            unsafe_allow_html=True)
            notes = st.text_area("Note aggiuntive", key="note")


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
                                'INDIC_DOC_SCANSIONARE': ', '.join(indic_doc_scansionare) if isinstance(indic_doc_scansionare, list) else indic_doc_scansionare,
                                'DETTAGLIO_RICHIESTA_INTERO': dettaglio_richiesta_intero,
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