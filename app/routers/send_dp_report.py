import smtplib
import os
import tempfile
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Union

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4

from sqlalchemy.orm import joinedload, selectinload
from .. import models
from ..database import SessionLocal

def send_email_with_attachment(subject: str, body: str, to_addr: Union[str, List[str]], from_addr: str, password: str, file_path: str, cc_emails: List[str] = None, ccn_emails: List[str] = None):
    """Invia un'email con un allegato PDF."""
    db = None # Inizializza db a None per la gestione del finally
    try:
        # Assumendo che SessionLocal() restituisca un oggetto sessione diretto
        # Se SessionLocal è un context manager (cioè supporta 'with'), usa:
        # with SessionLocal() as db:
        db = SessionLocal()
        
        msg = MIMEMultipart()
        msg['From'] = from_addr
        
        # Converte to_addr in una lista per uniformità
        to_recipients = [to_addr] if isinstance(to_addr, str) else to_addr
        # Filtra eventuali None o stringhe vuote dalla lista dei destinatari 'A'
        to_recipients_filtered = [email for email in to_recipients if email]
        
        if not to_recipients_filtered:
            print("Errore: Nessun destinatario 'A' valido specificato.")
            return # Termina la funzione se non ci sono destinatari validi

        msg['To'] = ", ".join(to_recipients_filtered)

        # Inizializza la lista di tutti i destinatari a cui inviare l'email (TO, CC, BCC)
        all_recipients_for_sendmail = list(to_recipients_filtered) 

        if cc_emails: # Controlla se la lista esiste e non è None
            cc_emails_filtered = [email for email in cc_emails if email] # Filtra None/stringhe vuote
            if cc_emails_filtered:
                msg['Cc'] = ", ".join(cc_emails_filtered)
                all_recipients_for_sendmail.extend(cc_emails_filtered) # Aggiungi alla lista combinata

        # I destinatari CCN (BCC) NON vengono aggiunti alle intestazioni del messaggio per motivi di privacy.
        # Vengono passati SOLO al server SMTP.
        if ccn_emails: # Controlla se la lista esiste e non è None
            ccn_emails_filtered = [email for email in ccn_emails if email] # Filtra None/stringhe vuote
            if ccn_emails_filtered:
                all_recipients_for_sendmail.extend(ccn_emails_filtered) # Aggiungi alla lista combinata

        # Aggiungi il corpo del testo
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Allega il file PDF
        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        encoders.encode_base64(part) # Codifica il payload
        part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(file_path)}")
        msg.attach(part)

        # Recupera la configurazione SMTP dal DB
        serverName_obj = db.query(models.Config).filter(models.Config.key == 'SMTP_SERVER').first()
        serverName = serverName_obj.value if serverName_obj else None

        serverPort_obj = db.query(models.Config).filter(models.Config.key == 'SMTP_PORT').first()
        # Assicurati che serverPort sia un int, con un fallback robusto
        serverPort = int(serverPort_obj.value) if serverPort_obj and serverPort_obj.value and str(serverPort_obj.value).isdigit() else None

        serverSSL_obj = db.query(models.Config).filter(models.Config.key == 'SMTP_SSL').first()
        # Converte il valore del DB in un booleano in modo robusto
        serverSSL = str(serverSSL_obj.value).lower() in ['true', '1'] if serverSSL_obj and serverSSL_obj.value is not None else False

        if not all([serverName, serverPort is not None]):
            print("Errore: Configurazione SMTP (Nome Server o Porta) non trovata o non valida nel database.")
            return # Termina la funzione se la configurazione è mancante

        print(f"serverName: {serverName}, serverPort: {serverPort}, serverSSL: {serverSSL}")
        
        server = None # Inizializza la variabile server
        try:
            if serverSSL:
                server = smtplib.SMTP_SSL(serverName, serverPort)
            else:
                server = smtplib.SMTP(serverName, serverPort)
                server.starttls() # Abilita TLS per connessioni non SSL dirette
            
            print("Connessione al server SMTP riuscita")
            server.login(from_addr, password)
            text = msg.as_string() # Ottieni il messaggio come stringa completa
            
            # INVIA L'EMAIL: il secondo argomento deve contenere TUTTI i destinatari (TO, CC, BCC)
            server.sendmail(from_addr, all_recipients_for_sendmail, text) 
            
            server.quit() # Chiudi la connessione SMTP
            print(f"Email con allegato inviata con successo a {', '.join(all_recipients_for_sendmail)}!")
        except smtplib.SMTPAuthenticationError as e:
            print(f"Errore di autenticazione SMTP: Verifica username e password. Dettagli: {e}")
            raise # Rilancia l'eccezione per notificare il chiamante
        except smtplib.SMTPConnectError as e:
            print(f"Errore di connessione SMTP: Verifica server e porta. Dettagli: {e}")
            raise
        except Exception as e:
            print(f"Errore generico nell'invio dell'email: {e}")
            raise
    finally:
        # Assicurati che la sessione del database sia chiusa anche in caso di errori
        if db:
            db.close()

def send_plain_text_email(subject, body, to_addr, from_addr, password):
    """Invia una semplice email di testo senza allegati."""
    try:
        db = SessionLocal()
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        serverName = db.query(models.Config).filter(models.Config.key == 'SMTP_SERVER').first()
        serverPort = db.query(models.Config).filter(models.Config.key == 'SMTP_PORT').first()
        serverSSL = db.query(models.Config).filter(models.Config.key == 'SMTP_SSL').first()
        try:
            server = smtplib.SMTP(serverName, serverPort)
            if serverSSL:
                server.starttls()
            server.login(from_addr, password)
            text = msg.as_string()
            server.sendmail(from_addr, to_addr, text)
            server.quit()
            print(f"Email di testo inviata con successo a {to_addr}!")
        except Exception as e:
            print(f"Errore nell'invio dell'email di testo a {to_addr}: {e}")
    finally:
        db.close()

def _header_footer(canvas, doc):
    """
    Aggiunge un'intestazione e un piè di pagina in stile Word a ogni pagina del PDF.
    """
    canvas.saveState()
    styles = getSampleStyleSheet()
    
    header_width = doc.width
    
    # --- Intestazione ---
    logo_path = 'path/to/your/logo.png'
    
    header_content = []
    
    # Titolo del report a sinistra
    report_title_p = Paragraph("<b>Report Giornaliero Attività</b>", styles['h2'])
    
    # Data e suffisso a destra
    date_text = f"<b>Daily Planning - {doc.giorno.strftime('%d/%m/%Y')}</b><br/><font size=9>{doc.title_suffix}</font>"
    date_p = Paragraph(date_text, ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))

    # Aggiungi il logo se esiste, altrimenti il titolo a sinistra
    if os.path.exists(logo_path):
        header_content.append(Image(logo_path, width=1.1*inch, height=0.4*inch))
    else:
        header_content.append(report_title_p)

    header_content.append(date_p)

    header_table = Table([header_content], colWidths=[header_width * 0.5, header_width * 0.5])
    
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    w, h = header_table.wrap(doc.width, doc.topMargin)
    header_table.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h + 15)
    
    canvas.setStrokeColor(colors.lightgrey)
    canvas.line(doc.leftMargin, doc.height + doc.topMargin - h + 10, doc.width + doc.leftMargin, doc.height + doc.topMargin - h + 10)

    # --- Piè di pagina ---
    footer_text = f"Pagina {doc.page}"
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 20, footer_text)
    
    canvas.restoreState()

def generate_dp_pdf(dp_testa: 'models.DPTesta', dp_details: list['models.DPDetail'], file_path: str, report_type: str, title_suffix: str = ""):
    """
    Genera un report PDF per il Daily Planning con layout professionale e differenziato.
    """
    doc = SimpleDocTemplate(file_path,
                            pagesize=A4, # Impostato a Verticale (Portrait)
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=1.0*inch, bottomMargin=0.8*inch)
    
    # Passa dati personalizzati a intestazione/piè di pagina
    doc.giorno = dp_testa.giorno if dp_testa and dp_testa.giorno else None # Ensure giorno can be None
    doc.title_suffix = title_suffix

    story = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SubHeader', fontSize=14, leading=16, spaceBefore=12, spaceAfter=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#002060')))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['Normal'], alignment=TA_LEFT, leading=14))
    styles.add(ParagraphStyle(name='TableCellBold', parent=styles['TableCell'], fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='TableCellSmall', parent=styles['TableCell'], fontSize=8, leftIndent=10))
    styles.add(ParagraphStyle(name='TableCellCenter', parent=styles['Normal'], alignment=TA_CENTER))

    # --- Suddivisione attività per fascia oraria ---
    # Ensure dp_details is not None before filtering
    details_to_process = dp_details if dp_details is not None else []

    def get_last_name(detail):
        # agpspm_user è una lista di utenti, ordina per il primo cognome disponibile
        if detail and isinstance(detail.agpspm_users, list) and len(detail.agpspm_users) > 0:
            # Prendi il primo utente e il suo last_name
            first_user = detail.agpspm_users[0]
            return (first_user.last_name or "") if hasattr(first_user, "last_name") else ""
        return ""

    am_details = sorted(
        [d for d in details_to_process if d.fasciaoraria and d.fasciaoraria.value == 'AM'],
        key=get_last_name
    )
    pm_details = sorted(
        [d for d in details_to_process if d.fasciaoraria and d.fasciaoraria.value == 'PM'],
        key=get_last_name
    )

    def create_timeslot_table(details, header_text):
        if not details:
            story.append(Paragraph(header_text, styles['SubHeader']))
            story.append(Paragraph("Nessuna attività pianificata per questa fascia oraria.", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            return

        story.append(Paragraph(header_text, styles['SubHeader']))
        
        available_width = doc.width
        if report_type == 'office':
            table_header = ["Risorsa","Cliente", "Sede", "Attività e Interventi", "Materiale", "Note"]
            colWidths = [
                available_width * 0.18,  # Risorsa
                available_width * 0.17,  # Cliente
                available_width * 0.17,  # Sede
                available_width * 0.26,  # Attività e Interventi
                available_width * 0.10,  # Materiale
                available_width * 0.12   # Note
            ]
        else: # report_type == 'resource'
            table_header = ["Cliente", "Sede", "Attività", "Interventi", "Materiale", "Note"]
            colWidths = [
                available_width * 0.18,  # Cliente
                available_width * 0.18,  # Sede
                available_width * 0.22,  # Attività
                available_width * 0.20,  # Interventi
                available_width * 0.10,  # Materiale
                available_width * 0.12   # Note
            ]

        table_data = [table_header]
        for detail in details:
           
            # Cliente Name
            cliente_name = "N/A"
            if detail.sedi and detail.sedi.cliente_ref and detail.sedi.cliente_ref.ragione_sociale:
                cliente_name = detail.sedi.cliente_ref.ragione_sociale
            cliente_p = Paragraph(cliente_name, styles['TableCell'])

            # Sede Description
            sede_desc = "N/A"
            if detail.sedi and detail.sedi.descrizione:
                sede_desc = detail.sedi.descrizione
                if sede_desc.lower() == '(la stessa)':
                    sede_desc = "Sede Principale" # Specific business rule
            sede_p = Paragraph(sede_desc, styles['TableCell'])
            
            # Material Status
            material_status = detail.materialedisponibile.value if detail.materialedisponibile else 'N/D'
            material_color = colors.green if material_status == 'SI' else colors.red
            material_paragraph = Paragraph(f'<b><font color="{material_color.hexval()}">{material_status}</font></b>', styles['TableCellCenter'])
            
            # Notes
            notes_p = Paragraph(detail.note or "", styles['TableCell']) # Empty string for no notes is often preferred over N/A

            if report_type == 'office':
                # Resource Name
                resource_name = "N/A"
                # agpspm_user è ora un array (lista di utenti)
                resource_names = []
                if detail.agpspm_users:
                    for user in detail.agpspm_users:
                        first_name = user.first_name or ""
                        last_name = user.last_name or ""
                        full_name = f"{first_name} {last_name}".strip()
                        if full_name:
                            resource_names.append(full_name)
                resource_name = ", ".join(resource_names) if resource_names else "N/A"
                resource_p = Paragraph(resource_name, styles['TableCell'])
                
                # Activity and Interventions for 'office'
                activity_cell_content = [Paragraph(detail.descrizionemanuale or "N/A", styles['TableCellBold'])]
                if detail.tipi_interventi_dettaglio:
                    for ti in detail.tipi_interventi_dettaglio:
                        desc = ti.tipo_intervento_ref.descrizione if ti.tipo_intervento_ref else "N/D"
                        qta_text = str(ti.qta) if ti.qta is not None else "N/A" # Handle qta potentially null
                        activity_cell_content.append(Paragraph(f"• {qta_text}x - {desc}", styles['TableCellSmall']))
                else:
                    activity_cell_content.append(Paragraph("<i>N/A</i>", styles['TableCellSmall'])) # No interventions
                table_data.append([resource_p, cliente_p, sede_p, activity_cell_content, material_paragraph, notes_p])
            
            else: # report_type == 'resource'
                # Activity for 'resource'
                activity_p = Paragraph(detail.descrizionemanuale or "N/A", styles['TableCell'])
                
                # Interventions for 'resource'
                interventions_content = []
                if detail.tipi_interventi_dettaglio:
                    for ti in detail.tipi_interventi_dettaglio:
                        desc = ti.tipo_intervento_ref.descrizione if ti.tipo_intervento_ref else "N/D"
                        qta_text = str(ti.qta) if ti.qta is not None else "N/A" # Handle qta potentially null
                        interventions_content.append(Paragraph(f"• {qta_text}x - {desc}", styles['TableCellSmall']))
                else:
                    interventions_content.append(Paragraph("<i>N/A</i>", styles['TableCellSmall'])) # No interventions
                table_data.append([cliente_p, sede_p, activity_p, interventions_content, material_paragraph, notes_p])
        
        table = Table(table_data, colWidths=colWidths)
        
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002060')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('TOPPADDING', (0,0), (-1,0), 10),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('GRID', (0,0), (-1,-1), 1, colors.darkgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F2F2F2')])
        ])
        table.setStyle(style)
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))

    create_timeslot_table(am_details, "Attività Mattina (AM)")
    create_timeslot_table(pm_details, "Attività Pomeriggio (PM)")
    
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

def send_initial_dp_emails(dp_testa_id: int):
    """
    Invia il report iniziale a uffici e a tutte le risorse coinvolte.
    """
    db = SessionLocal()
    try:
        print(f"Avvio del processo di invio email INIZIALE per DP ID: {dp_testa_id}")
        dp_testa = db.query(models.DPTesta).options(
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.agpspm_associations)
            .selectinload(models.DPDetailAGPSPM.agpspm_user),
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.sedi)
            .selectinload(models.Sede.cliente_ref),
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.tipi_interventi_dettaglio)
            .selectinload(models.DPDetailTI.tipo_intervento_ref)
        ).filter(models.DPTesta.id == dp_testa_id).first()

        if not dp_testa or not dp_testa.dettagli:
            print(f"Nessun DP trovato con ID {dp_testa_id}. Termino l'invio email iniziale.")
            return

        from_addr = db.query(models.Config).filter(models.Config.key == 'SMTP_USER').first().value
        password = db.query(models.Config).filter(models.Config.key == 'SMTP_PASS').first().value
        subject_prefix = f"Report Daily Planning del {dp_testa.giorno.strftime('%d/%m/%Y')}"
        temp_dir = tempfile.gettempdir()

        # 1. Invia PDF completo agli uffici
        full_report_path = os.path.join(temp_dir, f"dp_report_completo_{dp_testa_id}.pdf")
        generate_dp_pdf(dp_testa, dp_testa.dettagli, full_report_path, 'office', "Completo")
        offices_emails =  db.query(models.Config).filter(models.Config.key == 'EMAIL_CCN').first()
        if offices_emails:
            offices_emails = offices_emails.value.split(",")
        else:
            offices_emails = []

        send_email_with_attachment(subject_prefix, "In allegato il report completo del Daily Planning.", offices_emails, from_addr, password, full_report_path)


        # 2. Invia PDF personalizzati alle risorse
        # tasks_by_email = defaultdict(list)
        # for detail in all_details:
        #     if detail.id_agpspm: tasks_by_email[detail.id_agpspm].append(detail)
        
        # for resource_email, tasks in tasks_by_email.items():
        #     resource = tasks[0].agpspm_user
        #     resource_name = resource.first_name if resource else resource_email
            
        #     client_name_for_task = lambda d: d.sedi.cliente_ref.ragione_sociale if d.sedi and d.sedi.cliente_ref else "Cliente non specificato"
        #     task_list_str = "\n".join([f"- {d.descrizionemanuale} presso {client_name_for_task(d)}" for d in tasks])
        #     resource_body = f"Ciao {resource_name},\n\nQueste sono le tue attività del {dp_testa.giorno.strftime('%d/%m/%Y')}:\n{task_list_str}\n\nIn allegato il report del daily planning."

        #     send_email_with_attachment(f"{subject_prefix} - Attività per {resource_name}", resource_body, resource_email, from_addr, password, full_report_path)

        # try: os.remove(full_report_path)
        # except OSError as e: print(f"Errore rimozione file: {e}")

    finally:
        db.close()

def send_update_emails(dp_testa_id: int, affected_resources: List[str]):
    """
    Invia un'email di aggiornamento alle risorse impattate.
    - Se una risorsa ha nuove attività, invia un PDF aggiornato.
    - Se a una risorsa sono state rimosse tutte le attività, invia una notifica di testo.
    """
    db = SessionLocal()
    try:
        print(f"Avvio invio email di AGGIORNAMENTO per DP ID: {dp_testa_id} alle risorse: {affected_resources}")

        dp_testa = db.query(models.DPTesta).options(
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.agpspm_associations)
            .selectinload(models.DPDetailAGPSPM.agpspm_user),
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.sedi)
            .selectinload(models.Sede.cliente_ref),
            selectinload(models.DPTesta.dettagli)
            .selectinload(models.DPDetail.tipi_interventi_dettaglio)
            .selectinload(models.DPDetailTI.tipo_intervento_ref)
        ).filter(models.DPTesta.id == dp_testa_id).first()
        
        if not dp_testa:
            print(f"Nessun DP trovato con ID {dp_testa_id}. Termino l'invio email di aggiornamento.")
            return
        if not dp_testa.dettagli: return

        from_addr = db.query(models.Config).filter(models.Config.key == 'SMTP_USER').first().value
        password = db.query(models.Config).filter(models.Config.key == 'SMTP_PASS').first().value
        print(f"From: {from_addr}, Password: {password}")
        subject_prefix = f"AGGIORNAMENTO: Daily Planning del {dp_testa.giorno.strftime('%d/%m/%Y')}"
        temp_dir = tempfile.gettempdir()


        

        offices_emails =  db.query(models.Config).filter(models.Config.key == 'EMAIL_CCN').first()
        if offices_emails:
            offices_emails = offices_emails.value.split(",")
        else:
            offices_emails = []

        full_report_path = os.path.join(temp_dir, f"dp_report_completo_{dp_testa_id}.pdf")
        generate_dp_pdf(dp_testa, dp_testa.dettagli, full_report_path, 'office', "Completo")

        send_email_with_attachment(subject_prefix, "In allegato il report completo aggiornato del Daily Planning.", offices_emails, from_addr, password, full_report_path)

        # try: os.remove(full_report_path)
        # except OSError as e: print(f"Errore rimozione file: {e}")

        # for resource_email in affected_resources:
        #     # Recupera i dettagli dell'utente per ottenere il nome
        #     resource_user = db.query(models.OauthUser).filter(models.OauthUser.username == resource_email).first()
        #     resource_name = resource_user.first_name if resource_user else resource_email

        #     # Controlla le nuove attività per la risorsa
        #     tasks = db.query(models.DPDetail).options(
        #         joinedload(models.DPDetail.sedi).joinedload(models.Sede.cliente_ref),
        #         joinedload(models.DPDetail.agpspm_user),
        #         joinedload(models.DPDetail.tipi_interventi_dettaglio).joinedload(models.DPDetailTI.tipo_intervento_ref)
        #     ).filter(models.DPDetail.id_testata == dp_testa_id, models.DPDetail.id_agpspm == resource_email).all()

        #     if tasks:
        #         # Caso 1: La risorsa ha ancora attività (o nuove attività)
        #         body = f"Ciao {resource_name},\n\nLe tue attività per il giorno {dp_testa.giorno.strftime('%d/%m/%Y')} sono state aggiornate.\n\nControlla il PDF allegato per il tuo nuovo piano di lavoro."
        #         report_path = os.path.join(temp_dir, f"dp_report_aggiornato_{dp_testa_id}_{resource_email.split('@')[0]}.pdf")

        #         all_details = db.query(models.DPDetail).options(
        #             joinedload(models.DPDetail.sedi).joinedload(models.Sede.cliente_ref),
        #             joinedload(models.DPDetail.agpspm_user),
        #             joinedload(models.DPDetail.tipi_interventi_dettaglio).joinedload(models.DPDetailTI.tipo_intervento_ref)
        #         ).filter(models.DPDetail.id_testata == dp_testa_id).all()

        #         generate_dp_pdf(dp_testa, all_details, report_path, 'office', f"Aggiornato per {resource_name}")

        #         send_email_with_attachment(subject_prefix, body, resource_email, from_addr, password, report_path)
        #         try: os.remove(report_path)
        #         except OSError as e: print(f"Errore rimozione file: {e}")
        #     else:
        #         # Caso 2: Alla risorsa sono state rimosse tutte le attività
        #         body = f"Ciao {resource_name},\n\nLe tue attività per il giorno {dp_testa.giorno.strftime('%d/%m/%Y')} sono state aggiornate.\nNon hai più attività assegnate per questa data."
        #         send_plain_text_email(subject_prefix, body, resource_email, from_addr, password)

    finally:
        db.close()
