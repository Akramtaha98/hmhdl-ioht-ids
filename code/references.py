# -*- coding: utf-8 -*-
"""Master reference database for the HMHDL manuscript (47 entries: 4 Rosilah
Hassan / quantum-IoMT papers + 21 refs reused from the Introduction/Related
Work text + 22 refs integrated into the Methods section). REFS is ordered to
match the true, verified first-citation-in-text order of the built document
(confirmed by scanning the rendered .docx body in reading order); in-text
citation numbers and the printed References list are both derived directly
from this list index, so they stay in sync automatically as long as this
order matches the manuscript text.
"""

# Each entry: (key, ACS-style formatted citation text for the References list)
REFS = [
("orig1", "Choudhary, V.; Guha, P.; Pau, G.; Mishra, S. An Overview of Smart Agriculture "
     "Using Internet of Things (IoT) and Web Services. Environ. Sustain. Indic. 2025, 26, "
     "100607, doi:10.1016/j.indic.2025.100607."),
("orig2", "Rosca, C.; Stancu, A. The Impact of Cloud versus Local Infrastructure on "
     "Automatic IoT-Driven Hydroponic Systems. Appl. Sci. 2025, 15, 1–28."),
("orig4", "Zreikat, A. I.; Alarnaout, Z.; Abadleh, A.; Elbasi, E. The Integration of the "
     "Internet of Things (IoT) Applications into 5G Networks: A Review and Analysis. 2025, "
     "1–39."),
("orig5", "Wang, Z.; et al. Advanced Cellulose-Based Gels for Wearable Physiological "
     "Monitoring: From Fiber Modification to Application Optimization. Adv. Funct. Mater. "
     "2026, 36 (2), e15132, doi:10.1002/adfm.202515132."),
("orig3", "Azeez, N. A.; Ademoye, A. A.; Malomo, O. S. Investigation of Augmented Datasets "
     "for Security in Internet of Medical Things (IoMT) Ecosystems. Computers 2026, 15, 1–25."),
("hassan_iot_anomaly_2021",
     "Ahmad, Z.; Shahid Khan, A.; Nisar, K.; Haider, I.; Hassan, R.; Reazul Haque, M.; "
     "Tarmizi, S.; Rodrigues, J. J. P. C. Anomaly Detection Using Deep Neural Network for "
     "IoT Architecture. Appl. Sci. 2021, 11, 7050, doi:10.3390/app11157050."),
("hassan_iomt_survey_2024",
     "Tarish, H. A.; Hassan, R.; Ariffin, K. A. Z.; Jaber, M. M. Network Security Framework for "
     "Internet of Medical Things Applications: A Survey. J. Intell. Syst. 2024, 33 (1), 20220267, "
     "doi:10.1515/jisys-2023-0220."),
("hassan_fedcvae_2025",
     "Kazmi, S. H. A.; Hassan, R.; Qamar, F.; Nisar, K.; Al-Betar, M. A. Federated Conditional "
     "Variational Auto Encoders for Cyber Threat Intelligence: Tackling Non-IID Data in SDN "
     "Environments. IEEE Access 2025, 13, 26273–26288, doi:10.1109/ACCESS.2025.3529894."),
("quantum_iomt_2025",
     "Al-Mekhlaf, Z. G.; Saare, M. A.; Altmemi, J. M. H.; Al-Shareeda, M. A.; Mohammed, B. A.; "
     "Alshammari, G.; Alrashdi, R.; Alkhabra, Y. A.; Alreshidi, I. A Quantum-Resilient "
     "Lattice-Based Security Framework for Internet of Medical Things in Healthcare Systems. "
     "J. King Saud Univ. Comput. Inf. Sci. 2025, 37 (6), 126, doi:10.1007/s44443-025-00140-0."),

("orig6", "Pang, K.; Li, L.; Ouyang, W.; Liu, X.; Tang, Y. Establishment of ICU Mortality "
     "Risk Prediction Models with Machine Learning Algorithm Using MIMIC-IV Database. "
     "Diagnostics 2022, 12, 1–13."),
("orig7", "Din, S. U.; et al. Data Stream Classification with Novel Class Detection: A "
     "Review, Comparison and Challenges. Knowl. Inf. Syst. 2021, 63 (9), 2231–2276, "
     "doi:10.1007/s10115-021-01582-4."),
("orig8", "Al-Khamees, H.; Al-A'araji, N.; Al-Shamery, E. Data Stream: Statistics, "
     "Challenges, Concept Drift Detector Methods, Applications and Datasets. Int. J. Comput. "
     "Digit. Syst. 2023, 13, 717–728, doi:10.12785/ijcds/130157."),
("orig9", "Alomari, M.; Alsadah, S.; Aldahmash, N.; Alghulaygah, H.; Alogaiel, R.; "
     "Saqib, N. A. A Comprehensive Review of Distributed Denial-of-Service (DDoS) Attacks: "
     "Techniques and Mitigation Strategies. In 2024 Seventh International Women in Data "
     "Science Conference at Prince Sultan University (WiDS PSU); 2024; pp 215–222, "
     "doi:10.1109/WiDS-PSU61003.2024.00051."),
("orig10", "Abiramasundari, S.; Ramaswamy, V. Distributed Denial-of-Service (DDoS) Attack "
     "Detection Using Supervised Machine Learning Algorithms. 2025."),
("orig11", "Hazman, C.; Douiba, M.; Guezzaz, A.; Ravi, V.; Azrour, M.; Benkirane, S. "
     "Intrusion Detection Approaches in Healthcare Systems: An Overview. In Reliability in "
     "Cyber-Physical Systems: The Human Factor Perspective; Springer Nature Switzerland: "
     "Cham, 2026; pp 131–145, doi:10.1007/978-3-032-09917-4_9."),
("orig12", "Yacoubi, M.; Moussaoui, O.; Drocourt, C. AI for IoMT Security: A Comprehensive "
     "Survey of Intrusion Detection and System Architectures. Internet of Things 2026, 36, "
     "101869, doi:10.1016/j.iot.2025.101869."),
("orig13", "Thiyagu, T.; Krishnaveni, S. Advanced Intrusion Detection in Internet of "
     "Things-Driven Health Care with Adaptive Generative Vision Transformer Network and "
     "Generative Vision Transformers. Knowl. Inf. Syst. 2025, 67 (12), 11481–11513, "
     "doi:10.1007/s10115-025-02566-4."),
("orig14", "Radwan, M.; Ali, A.; Abdelhameed, A. Potato Leaf Disease Classification Using "
     "Optimized Machine Learning. Potato Res. 2025, 68 (2), 897–921, "
     "doi:10.1007/s11540-024-09763-8."),
("orig15", "Mienye, I.; Jere, N. A Survey of Decision Trees: Concepts, Algorithms, and "
     "Applications. IEEE Access 2024, 12, 86716–86727, doi:10.1109/ACCESS.2024.3416838."),
("orig16", "Wang, Y.; Du, J.; Shao, Y. A Novel Support Vector Machine with Hillside Loss "
     "and Margin Distribution. Eur. J. Oper. Res. 2026, 334 (3), 751–763, "
     "doi:10.1016/j.ejor.2026.04.049."),
("orig17", "Purwono, W.; Ma'arif, A.; Rahmaniar; Imam, H.; Fathurrahman, K.; Zatu, A.; "
     "Frisky, K. Understanding of Convolutional Neural Network (CNN): A Review. Int. J. "
     "Robot. Control Syst. 2022, 2 (4), 739–748."),
("orig18", "Krichen, M.; Mihoub, A. Long Short-Term Memory Networks: A Comprehensive "
     "Survey. AI 2025, 1–21."),
("orig19", "Hussain, J.; Båth, M.; Ivarsson, J. Generative Adversarial Networks in "
     "Medical Image Reconstruction: A Systematic Literature Review. Comput. Biol. Med. 2025, "
     "191, 110094, doi:10.1016/j.compbiomed.2025.110094."),
("orig20", "Maji, P.; Mullins, R. On the Reduction of Computational Complexity of Deep "
     "Convolutional Neural Networks. Entropy 2018, 20 (4), doi:10.3390/e20040305."),
("orig21", "Saputra, N. A.; Riza, L. S.; Setiawan, A.; Hamidah, I. A Systematic Review "
     "for Classification and Selection of Deep Learning Methods. Decis. Anal. J. 2024, 12, "
     "100489, doi:10.1016/j.dajour.2024.100489."),
("orig22", "Mo, S.; et al. From Global to Local: A Lightweight CNN Approach for Long-Term "
     "Time Series Forecasting. Comput. Electr. Eng. 2025, 123, 110192, "
     "doi:10.1016/j.compeleceng.2025.110192."),
("orig23", "Nosouhian, S.; Nosouhian, F.; Khoshouei, A. A Review of Recurrent Neural "
     "Network Architecture for Sequence Learning: Comparison between LSTM and GRU. 2021, "
     "doi:10.20944/preprints202107.0252.v1."),
("orig24", "Shabrawy, M.; El-Kenawy, E.-S. M.; Abdel-Hamid, N. B.; Abdelsalam, M. M. An "
     "Optimization-Driven Hierarchical Deep Learning Approach Using the Gray Langurs "
     "Algorithm for Data-Driven Seismic Activity Prediction. Sci. Rep. 2026, 16 (1), 18846, "
     "doi:10.1038/s41598-026-56169-2."),
("orig25", "Khan, W.; Nabilal, K. V.; Ishrat, M.; Asad, K.; Ahmad, F.; Wagh, M. S. A "
     "Multi-Stage Hybrid Framework for Anomaly Detection in Attributed Graphs Using "
     "Attention-Driven Representation and Community-Aware Scoring. Discov. Appl. Sci. 2025, "
     "7 (10), 1203, doi:10.1007/s42452-025-07801-9."),
("orig26", "Karboub, K.; Tabaa, M. A Machine Learning Based Discharge Prediction of "
     "Cardiovascular Diseases Patients in Intensive Care Units. Healthcare 2022, 10, 1–23."),
("orig27", "Hempel, L.; Sadeghi, S.; Kirsten, T. Prediction of Intensive Care Unit Length "
     "of Stay in the MIMIC-IV Dataset. Appl. Sci. 2023, 13, 6930."),
("orig28", "Koumantakis, E.; et al. Deep Learning Models for ICU Readmission Prediction: "
     "A Systematic Review and Meta-Analysis. Crit. Care 2025, 1–13."),
("orig29", "Krishna Kumari, M. S. R.; Komala, C. R.; Afreen Banu, E.; Sivaramkrishnan, M.; "
     "Ramkumar, A. Z. S. I.; Sekar, K.; Muzammil, K. Hybrid Optimization-Based Quantum-Driven "
     "Multi-Relational Graph Attention Networks for Enhanced Cyber Attack Detection in "
     "Medical IoT Networks. Sci. Rep. 2026."),
("orig30", "Vijayakumar, K. P.; Pradeep, K.; Prusty, M. R. Enhanced Cyber Attack Detection "
     "Process for Internet of Health Things (IoHT) Devices Using Deep Neural Network. "
     "Processes 2023, 11."),
("orig31", "Areia, J.; Bispo, I. V. O. A.; Santos, L.; Costa, R. L. D. E. C. IoMT-TrafficData: "
     "Dataset and Tools for Benchmarking Intrusion Detection in Internet of Medical Things. "
     "IEEE Access 2024, 12, doi:10.5281/zenodo.8116337."),
("orig32", "Algethami, S. A.; Alshamrani, S. S. A Deep Learning-Based Framework for "
     "Strengthening Cybersecurity in Internet of Health Things (IoHT) Environments. "
     "Appl. Sci. 2024, 14."),
("orig33", "Alohali, M. A.; Alamgeer, M.; Al-sharafi, A. M.; Asklany, S. A. Improving "
     "Internet of Health Things Security through Anomaly Detection Framework Using "
     "Artificial Intelligence Driven Ensemble Approaches. Sci. Rep. 2025, 15, 1–23."),
("orig34", "Mosaiyebzadeh, F.; Pouriyeh, S.; Han, M.; Liu, L.; Xie, Y. Privacy-Preserving "
     "Federated Learning-Based Intrusion Detection System for IoHT Devices. Electronics "
     "2025, 14 (67), 1–18."),
("orig35", "Alharbi, R. M.; Khan, M. A. Analyzing Cyber Attack Detection in IoT Healthcare "
     "Environments Using Artificial Intelligence. Int. J. Adv. Comput. Sci. Appl. 2025, "
     "16 (8), 412–423."),
("orig36", "Tauqeer, H.; Iqbal, M. M.; Ali, A.; Zaman, S.; Chaudhry, M. U. Cyberattacks "
     "Detection in IoMT Using Machine Learning Techniques. J. Comput. Biomed. Informatics "
     "2022, 4 (1), 13–20, doi:10.56979/401/2022/80."),
("orig37", "Judith, A.; Kathrine, G. J. W.; Silas, S.; Andrew, J. Efficient Deep "
     "Learning-Based Cyber-Attack Detection for Internet of Medical Things Devices. "
     "Eng. Proc. 2023, 59 (139)."),
("orig38", "Shaikh, J. A.; et al. RCLNet: An Effective Anomaly-Based Intrusion Detection "
     "for Securing the IoMT System. Digit. Health 2024, 1–12, doi:10.3389/fdgth.2024.1467241."),
("orig39", "Wu, W.; Fouzi, H.; Sidi-Mohammed, S. Improving Cyber-Attack Detection in "
     "Internet of Medical Things Using Ensemble Deep Learning Methods. Clust. Comput. 2025, "
     "28, doi:10.1007/s10586-025-05660-y."),
("orig40", "Balhareth, G.; Ilyas, M.; Alkanjr, B. ML-FSID-FIS: A Multi-Level Feature "
     "Selection and Fuzzy Inference System for Intrusion Detection in IoMT. Sensors 2026, "
     "1–21."),
("orig41", "Abid, M. B. A Trust-Based Ensemble Machine Learning Framework for Intrusion "
     "Detection in Medical Internet of Things. Spectr. Eng. Sci. 2026, 4 (4), 3007–3012."),
("orig42", "Aversano, L.; Galantucci, S.; Porcelli, A. SurIoT: Automatic Generation of "
     "Internet-of-Medical-Things Network Intrusion Detection and Prevention Rules. "
     "Int. J. Inf. Secur. 2026, 123."),
("orig43", "Abdelhaq, M.; Palanisamy, S. K.; Gopinath, M.; Manasa, V. G. S.; Alsaqour, R.; "
     "Manickam, S. A Hybrid XGBoost–SVM Ensemble Framework for Robust Cyber-Attack Detection "
     "in the Internet of Medical Things (IoMT). Sci. Rep. 2026."),

]

KEY_TO_NUM = {key: i + 1 for i, (key, _) in enumerate(REFS)}

# Mapping from the ORIGINAL document's [n] bracket numbers (1-43, as embedded
# throughout the reused Introduction/Related Work paragraph text, including
# single numbers, comma lists, and en-dash ranges) to this manuscript's new
# reference keys/numbers.
OLD_NUM_TO_KEY = {n: f"orig{n}" for n in range(1, 44)}


def cite(*keys):
    """Return an in-text citation string like '[4]' or '[7,9]' for one or more ref keys."""
    nums = sorted(KEY_TO_NUM[k] for k in keys)
    return "[" + ",".join(str(n) for n in nums) + "]"
