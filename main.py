import os
import xml.etree.ElementTree as ET
from deep_translator import GoogleTranslator
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing

# Flag per indicare se è stato richiesto l'interruzione del programma
interrupted = False
translation_cache = {}


def translate_xml_file(filename, target_lang='it'):
    # Parsing dell'XML
    tree = ET.parse(filename)
    root = tree.getroot()

    # Funzione per tradurre testo usando GoogleTranslator
    def translate_text(text):
        if text in translation_cache:
            return translation_cache[text]

        if len(text) <= 4000:
            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            translation_cache[text] = translated
            return translated
        else:
            # Suddivisione del testo in segmenti di massimo 4000 caratteri
            parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]

            # Traduzione parallela dei segmenti
            translated_parts = []
            with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 2) as executor:
                futures = [executor.submit(GoogleTranslator(source='auto', target=target_lang).translate, part) for part
                           in parts]
                for future in as_completed(futures):
                    try:
                        translated_parts.append(future.result())
                    except Exception as e:
                        print(f"Errore durante la traduzione di una parte: {e}")

            translated = ''.join(translated_parts)
            translation_cache[text] = translated
            return translated

    # Funzione ricorsiva per navigare l'albero XML e tradurre i testi
    def translate_element(element, progress_bar, total_elements, processed_elements):
        global interrupted  # Usiamo la variabile globale per gestire l'interruzione

        # Traduzione del testo nel tag attuale
        if element.text and element.text.strip():
            element.text = translate_text(element.text.strip())
            processed_elements[0] += 1
            progress_bar.update(1)  # Aggiorna la barra di avanzamento
            progress_bar.set_postfix({'% completato': f"{(processed_elements[0] / total_elements) * 100:.2f}%",
                                      'tempo stimato': f"{progress_bar.format_dict['elapsed'] / processed_elements[0] * (total_elements - processed_elements[0]):.2f} s"})
        # Traduzione degli attributi
        for key, value in element.attrib.items():
            if value.strip():
                element.set(key, translate_text(value.strip()))
                processed_elements[0] += 1
                progress_bar.update(1)  # Aggiorna la barra di avanzamento
                progress_bar.set_postfix({'% completato': f"{(processed_elements[0] / total_elements) * 100:.2f}%",
                                          'tempo stimato': f"{progress_bar.format_dict['elapsed'] / processed_elements[0] * (total_elements - processed_elements[0]):.2f} s"})
        # Traduzione dei sotto-elementi
        for child in element:
            translate_element(child, progress_bar, total_elements, processed_elements)

        # Se l'interruzione è stata richiesta, salviamo il file prima di uscire
        if interrupted:
            save_translated_file(tree, filename)

    # Funzione per gestire il segnale di interruzione (Ctrl+C)
    def handle_interrupt(signum, frame):
        global interrupted
        interrupted = True
        print("\nInterruzione richiesta. Salvataggio del file in corso...")

    # Cattura del segnale di interruzione (Ctrl+C)
    signal.signal(signal.SIGINT, handle_interrupt)

    try:
        # Calcola il numero totale di elementi da tradurre
        total_elements = sum(1 for _ in root.iter())
        processed_elements = [0]

        # Crea una barra di avanzamento
        with tqdm(total=total_elements, desc="Progresso totale", unit="elemento") as progress_bar:
            # Traduzione dell'intero XML
            translate_element(root, progress_bar, total_elements, processed_elements)
    except Exception as e:
        print(f"Errore durante la traduzione: {e}")
    finally:
        save_translated_file(tree, filename)
        print("Processo completato e file salvato.")


def save_translated_file(tree, original_filename):
    # Salvataggio del file tradotto (aggiungendo '_translated' al nome)
    output_filename = os.path.splitext(original_filename)[0] + '_translated.xml'
    with open(output_filename, 'w', encoding='utf-8') as f:
        tree.write(f, encoding='unicode', xml_declaration=True)
    print(f"File tradotto salvato come: {output_filename}")


if __name__ == "__main__":
    # Nome del file XML da tradurre
    xml_file = "file.xml"

    # Traduzione dell'XML specificato
    translate_xml_file(xml_file)
