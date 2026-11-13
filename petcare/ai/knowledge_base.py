"""Curated, reviewed pet-care knowledge base with Okapi BM25 retrieval and vet-safety guardrails."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from petcare.ai.contracts import KnowledgeCitation, SafetyNotice
from petcare.services.catalog_intent import _normalize


BM25_K1 = 1.5
BM25_B = 0.75
MIN_BM25_SCORE = 2.2

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "my", "of", "on", "or", "should", "so", "that", "the",
    "their", "to", "what", "when", "which", "with", "your",
    "ba", "ban", "bao", "bi", "cach", "can", "cho", "co", "cua", "de", "duoc", "gi",
    "hay", "khi", "khong", "la", "lam", "minh", "mot", "nao", "nay", "nen", "nhu", "nhung",
    "nuoi", "o", "phai", "ra", "sao", "se", "tai", "the", "thi", "toi", "trong", "va", "ve", "voi",
}


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Reviewed, versioned pet-care reference article."""

    doc_id: str
    topic: str
    species_scope: str  # "cat" | "dog" | "both"
    title_vi: str
    title_en: str
    source_name: str
    source_url: str
    updated_at: str
    review_status: str
    version: str
    keywords: tuple[str, ...]
    summary_vi: str
    summary_en: str
    bullets_vi: tuple[str, ...]
    bullets_en: tuple[str, ...]


@dataclass(slots=True)
class KnowledgeRetrievalResult:
    """Grounded retrieval output with citations and mandatory non-vet disclaimer."""

    matched: bool
    reply: str
    citations: list[KnowledgeCitation]
    safety_notice: SafetyNotice
    follow_up_questions: list[str]


KNOWLEDGE_CORPUS: tuple[KnowledgeDocument, ...] = (
    KnowledgeDocument(
        doc_id="KB-NUTR-001",
        topic="feeding_practices",
        species_scope="both",
        title_vi="Nguyên tắc cho chó mèo ăn theo độ tuổi và chuyển đổi thức ăn 7–10 ngày",
        title_en="Life-Stage Feeding Practices & Safe 7–10 Day Diet Transition",
        source_name="WSAVA Global Nutrition Guidelines",
        source_url="https://wsava.org/global-guidelines/global-nutrition-guidelines/",
        updated_at="2025-06-15",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "feeding", "schedule", "meals", "transition", "switch food", "kibble", "wet food", "pate",
            "adult", "kitten", "puppy", "portion", "water", "hydration",
            "cho an", "lich cho an", "may bua", "chuyen doi thuc an", "doi hat", "khau phan", "nuoc uong",
        ),
        summary_vi=(
            "Khẩu phần ăn cần phù hợp đúng loài (chó hoặc mèo) và giai đoạn sống (thú non đang lớn hay trưởng thành), "
            "đồng thời luôn có sẵn nước sạch mỗi ngày."
        ),
        summary_en=(
            "Daily feeding should match species and life stage (growing kitten/puppy vs adult maintenance), "
            "with clean fresh water accessible at all times."
        ),
        bullets_vi=(
            "Thú non (<12 tháng) thường cần chia 3–4 bữa nhỏ/ngày giàu năng lượng; thú trưởng thành thường ăn 2 bữa ổn định/ngày hoặc theo hướng dẫn bao bì.",
            "Khi đổi sang loại hạt/pate mới, hãy trộn tăng dần trong 7–10 ngày (25% → 50% → 75% → 100%) để hạn chế rối loạn tiêu hóa.",
            "Kết hợp thức ăn ướt (pate) hoặc đài phun nước giúp mèo tăng lượng nước tiêu thụ tự nhiên.",
            "Bánh thưởng (treats) không nên vượt quá 10% tổng năng lượng khẩu phần hàng ngày.",
        ),
        bullets_en=(
            "Growing puppies and kittens (<12 months) typically benefit from 3–4 smaller meals/day; healthy adults commonly eat 2 measured meals/day per package feeding charts.",
            "Transition to any new food gradually over 7–10 days (25% → 50% → 75% → 100%) to minimize digestive upset.",
            "Incorporating wet food pouches or circulating water bowls helps support feline hydration.",
            "Keep training treats below 10% of total daily caloric intake.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-SAFE-002",
        topic="feeding_practices",
        species_scope="both",
        title_vi="Thực phẩm và cây trồng phổ biến trong nhà gây ngộ độc cho chó mèo",
        title_en="Common Household Foods & Plants Toxic to Dogs and Cats",
        source_name="ASPCA Animal Poison Control",
        source_url="https://www.aspca.org/pet-care/animal-poison-control/people-foods-avoid-feeding-your-pets",
        updated_at="2025-08-01",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "toxic", "poison", "unsafe food", "chocolate", "xylitol", "grapes", "raisins",
            "onion", "garlic", "lily", "lilies", "bones", "human food",
            "thuc pham nguy hiem", "khong nen cho an", "ngo doc", "socola", "nho kho", "hanh toi", "hoa ly", "xuong",
        ),
        summary_vi=(
            "Nhiều thực phẩm an toàn với người lại gây ngộ độc cấp tính cho chó mèo; tuyệt đối không tự cho ăn thức ăn thừa nhiều gia vị."
        ),
        summary_en=(
            "Several everyday human foods and ornamental plants are acutely toxic to pets and must be kept strictly out of reach."
        ),
        bullets_vi=(
            "Tuyệt đối tránh: sô-cô-la (caffeine/theobromine), chất tạo ngọt xylitol, nho tươi/nho khô, hành, tỏi, hẹ, hạt mắc-ca, rượu bia và xương nấu chín dễ vỡ dăm.",
            "Với mèo: mọi bộ phận của hoa ly (Lilium/Hemerocallis), kể cả phấn hoa hoặc nước cắm bình, đều có nguy cơ gây suy thận cấp nghiêm trọng.",
            "Tuyệt đối không dùng thuốc giảm đau của người (như paracetamol/acetaminophen, ibuprofen) cho chó mèo.",
            "Nếu nghi ngờ thú cưng vừa nuốt chất độc, cần đưa tới phòng khám thú y ngay lập tức kèm vỏ/nhãn sản phẩm.",
        ),
        bullets_en=(
            "Strictly avoid chocolate, xylitol (birch sugar), grapes/raisins, onions, garlic, chives, macadamia nuts, alcohol, raw yeast dough, and cooked splintering bones.",
            "For cats: true lilies and daylilies (petals, leaves, pollen, even vase water) can cause life-threatening acute kidney injury.",
            "Never administer human pain relievers such as acetaminophen (paracetamol) or ibuprofen to pets.",
            "If toxin ingestion is suspected, contact a veterinarian immediately and bring the product label.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-GROOM-003",
        topic="grooming_basics",
        species_scope="both",
        title_vi="Chăm sóc lông, tắm đúng cách, cắt móng và vệ sinh răng tai cơ bản",
        title_en="Coat Brushing, Bathing, Nail Trimming & Preventive Dental/Ear Care",
        source_name="AVMA Pet Care Guidelines",
        source_url="https://www.avma.org/resources-tools/pet-owners/petcare",
        updated_at="2025-05-20",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "groom", "grooming", "brush", "coat", "bath", "bathing", "shampoo", "nail", "clipper",
            "teeth", "dental", "toothpaste", "ear", "eye", "long coat", "short coat",
            "chai long", "tam", "sua tam", "cat mong", "ve sinh rang", "danh rang", "ve sinh tai", "lau mat", "cham soc long",
        ),
        summary_vi=(
            "Chăm sóc vệ sinh định kỳ giúp phát hiện sớm các bất thường ở da, tai, răng miệng và giữ bộ lông sạch khỏe."
        ),
        summary_en=(
            "Routine home grooming keeps skin and coat healthy while helping owners spot early skin, ear, or dental issues."
        ),
        bullets_vi=(
            "Chải lông: giống lông dài/dày/xù nên chải mỗi ngày hoặc cách ngày để ngừa vón cục; lông ngắn chải 1–2 lần/tuần.",
            "Tắm rửa: chỉ dùng sữa tắm cân bằng pH dành riêng cho chó mèo (không dùng dầu gội người); sấy khô kỹ chân lông sau khi tắm.",
            "Răng miệng: tập đánh răng bằng kem đánh răng chuyên dụng cho thú cưng (không chứa fluoride/xylitol).",
            "Cắt móng & tai mắt: bấm phần đầu móng trong/trắng, tránh cắt phạm phần tủy hồng (quick); lau vành tai ngoài bằng dung dịch chuyên dụng, không ngoáy sâu tăm bông vào ống tai.",
        ),
        bullets_en=(
            "Brushing: long, curly, or dense double coats need daily or every-other-day brushing to prevent painful mats; short coats benefit from 1–2 sessions weekly.",
            "Bathing: always use pH-balanced pet shampoo rather than human soap, and dry the undercoat thoroughly afterward.",
            "Dental care: acclimate pets gradually to pet-safe enzymatic toothpaste—never human fluoride/xylitol toothpaste.",
            "Nails & ears: trim only the curved tip safely away from the pink vascular quick; wipe outer ear flaps gently with pet ear cleaner without inserting swabs deep into the canal.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-ENV-004",
        topic="environmental_preparation",
        species_scope="cat",
        title_vi="Chuẩn bị căn hộ cho mèo và quy tắc khay vệ sinh N + 1",
        title_en="Apartment Preparation for Cats & The N + 1 Litter Box Rule",
        source_name="AAFP / ISFM Feline Environmental Needs Guidelines",
        source_url="https://catvets.com/guidelines/practice-guidelines/environmental-needs-guidelines",
        updated_at="2025-07-10",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "apartment", "indoor cat", "litter box", "litter", "prepare", "new cat", "balcony", "window",
            "vertical space", "cat tree", "scratching post", "safe room",
            "can ho", "chung cu", "meo trong nha", "khay ve sinh", "chuan bi can ho", "chuan bi nha", "moi don meo", "luoi an toan", "ban cong",
        ),
        summary_vi=(
            "Mèo sống hoàn toàn trong căn hộ cần không gian an toàn ở ban công/cửa sổ, góc ẩn nấp yên tĩnh và bố trí khay vệ sinh tách biệt chỗ ăn uống."
        ),
        summary_en=(
            "Indoor apartment cats thrive when vertical territory, balcony/window safety screens, quiet resting zones, and clean litter stations are prepared before arrival."
        ),
        bullets_vi=(
            "An toàn căn hộ: lắp lưới bảo vệ ban công/cửa sổ chắc chắn, bọc dây điện hở và dọn sạch cây cảnh độc (như hoa ly, trầu bà).",
            "Quy tắc khay vệ sinh N + 1: số khay nên bằng số mèo cộng thêm 1 (ví dụ 1 mèo nên có 2 khay ở vị trí thoáng, tách xa bát thức ăn và nước uống); xúc dọn chất thải mỗi ngày.",
            "Giai đoạn làm quen: chuẩn bị 1 phòng yên tĩnh trong vài ngày đầu với ổ nằm, nước, thức ăn và khay cát quen mùi trước khi mở rộng toàn căn hộ.",
            "Bố trí trụ cào móng vững chắc và kệ leo cao để mèo giải tỏa bản năng tự nhiên trong không gian hẹp.",
        ),
        bullets_en=(
            "Apartment safety: secure all windows and balconies with sturdy pet mesh, conceal loose cords, and remove toxic houseplants before arrival.",
            "N + 1 litter box rule: provide one box per cat plus one extra in quiet, accessible spots well separated from food and water bowls; scoop daily.",
            "Decompression zone: start new cats in a calm starter room with bedding, water, food, and litter for the first few days before gradual apartment exploration.",
            "Provide sturdy scratching posts and vertical perches/shelves to expand usable living territory.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-ENR-005",
        topic="pet_enrichment",
        species_scope="both",
        title_vi="Vận động thể chất, trò chơi trí tuệ và giảm căng thẳng cho chó mèo",
        title_en="Daily Enrichment, Interactive Play & Stress Reduction for Dogs and Cats",
        source_name="Cornell Feline Health Center & ASPCA Enrichment Guides",
        source_url="https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center",
        updated_at="2025-07-22",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "enrichment", "play", "exercise", "boredom", "mental stimulation", "feather wand",
            "walk", "leash", "indoor", "puzzle", "energy", "stress",
            "van dong", "do choi", "can cau meo", "dat di dao", "giam cang thang", "nham chan", "nang luong", "tro choi",
        ),
        summary_vi=(
            "Hoạt động chơi tương tác và kích thích khứu giác/trí tuệ hàng ngày giúp giảm buồn chán, hạn chế phá đồ và duy trì cân nặng khỏe mạnh."
        ),
        summary_en=(
            "Consistent physical play and foraging/scent enrichment prevent boredom-related behaviors and support healthy body condition."
        ),
        bullets_vi=(
            "Với mèo: chia 2–3 phiên chơi ngắn (10–15 phút/phiên) bằng cần câu lông vũ mô phỏng chu trình săn mồi, kết thúc bằng việc cho bắt được đồ chơi và ăn bữa nhỏ.",
            "Luân phiên cất/đổi đồ chơi mỗi tuần và cất gọn đồ chơi có dây mảnh sau khi chơi để tránh nuốt dị vật.",
            "Với chó: kết hợp đi dạo có dây dắt an toàn với các bài tập đánh hơi tìm bánh thưởng và rèn lệnh cơ bản ngắn gọn.",
        ),
        bullets_en=(
            "For cats: run 2–3 short interactive wand-toy sessions (10–15 minutes) mimicking hunt-catch-eat, letting the cat catch the toy before offering a small meal.",
            "Rotate toys weekly to keep novelty high, and store string/feather wands safely out of reach after supervised play to prevent ingestion.",
            "For dogs: pair safe leashed walks with sniff-walks, food puzzles, and short positive-reinforcement training games.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-BEH-006",
        topic="basic_behavior",
        species_scope="both",
        title_vi="Hiểu ngôn ngữ cơ thể cơ bản và huấn luyện củng cố tích cực",
        title_en="Basic Pet Body Language & Positive-Reinforcement Socialization",
        source_name="AVMA Animal Welfare & Behavior Resources",
        source_url="https://www.avma.org/resources-tools/pet-owners/petcare/selecting-pet-dog",
        updated_at="2025-04-18",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "behavior", "behaviour", "scratching", "barking", "chewing", "biting", "training",
            "socialization", "stress", "hiding", "body language", "reward",
            "hanh vi", "cao sofa", "sua", "can pha", "huan luyen", "nhut nhat", "tron", "ngon ngu co the", "khen thuong",
        ),
        summary_vi=(
            "Sử dụng khen thưởng kịp thời (bánh thưởng nhỏ, lời khen) thay cho quát phạt giúp thú cưng xây dựng sự tin cậy và thói quen tốt bền vững."
        ),
        summary_en=(
            "Reward-based training and respect for stress signals build trust safely, whereas punishment increases fear and defensive behavior."
        ),
        bullets_vi=(
            "Dấu hiệu căng thẳng cần cho bé không gian nghỉ: cụp tai, thu mình, liếm môi liên tục, quẫy mạnh chóp đuôi (ở mèo) hoặc gồng cứng người.",
            "Khi mèo cào đồ nội thất hoặc chó gặm đồ: đặt trụ cào/đồ gặm an toàn ngay cạnh vị trí đó và thưởng ngay khi bé dùng đúng chỗ.",
            "Nếu hành vi thay đổi đột ngột (bỗng nhiên đi vệ sinh sai chỗ, hung dữ hoặc trốn kỹ), cần khám thú y trước để loại trừ nguyên nhân đau/bệnh lý.",
        ),
        bullets_en=(
            "Watch for stress cues—flattened ears, tucked tail, lip-licking, crouching, or tail thrashing in cats—and allow calm space rather than forcing handling.",
            "Redirect scratching or chewing by placing appropriate scratching posts or safe chew items next to target areas and rewarding desired use immediately.",
            "Sudden behavior changes (house-soiling, hiding, irritability) warrant a veterinary checkup to rule out underlying pain or illness.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-OWN-007",
        topic="responsible_ownership",
        species_scope="both",
        title_vi="Checklist nhận nuôi / chọn mua thú cưng có trách nhiệm",
        title_en="Responsible Pet Purchasing & Ownership Readiness Checklist",
        source_name="AVMA Responsible Pet Ownership Guidelines",
        source_url="https://www.avma.org/resources-tools/pet-owners/petcare/responsible-pet-ownership",
        updated_at="2025-09-01",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "responsible", "adoption", "buying", "choose a pet", "first time", "budget", "checkup",
            "vaccine", "temperament", "breed", "checklist",
            "co trach nhiem", "chon mua", "nhan nuoi", "lan dau nuoi", "moi nuoi", "chi phi", "kham thu y", "tiem phong", "luu y khi chon mua",
        ),
        summary_vi=(
            "Nuôi thú cưng là cam kết dài hạn 10–15+ năm; cần đánh giá trung thực quỹ thời gian, không gian sống, chi phí định kỳ và kiểm tra trực tiếp từng cá thể."
        ),
        summary_en=(
            "Pet ownership is a 10–15+ year commitment requiring realistic planning for daily care time, living environment, ongoing expenses, and routine veterinary care."
        ),
        bullets_vi=(
            "Không chọn thú cưng chỉ dựa theo định kiến về giống: tính cách, mức năng lượng và độ dạn người khác nhau ở từng cá thể và cần quan sát thực tế.",
            "Dự trù ngân sách định kỳ ngoài giá mua ban đầu: thức ăn, cát/vệ sinh, khám sức khỏe định kỳ, tiêm phòng, tẩy ký sinh trùng và quỹ dự phòng thú y.",
            "Kiểm tra rõ thông tin hồ sơ đã xác minh tại cửa hàng (độ tuổi, cân nặng, tình trạng ăn uống) và đặt lịch khám kiểm tra đầu tiên với bác sĩ thú y.",
        ),
        bullets_en=(
            "Never assume temperament or apartment suitability from breed stereotypes alone—observe the individual animal's documented traits and in-person demeanor.",
            "Budget beyond initial purchase price for recurring nutrition, litter/hygiene supplies, routine wellness exams, parasite prevention, and emergency reserves.",
            "Review verified profile records (age, weight, feeding habits) and schedule an initial wellness exam with a licensed veterinarian.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-PROD-008",
        topic="product_selection",
        species_scope="both",
        title_vi="Lưu ý khi chọn thức ăn, cát vệ sinh và phụ kiện theo thông tin xác thực",
        title_en="How to Evaluate Pet Food, Litter & Accessories Using Verified Metadata",
        source_name="WSAVA Selecting a Pet Food & Pet Retail Safety Standards",
        source_url="https://wsava.org/wp-content/uploads/2021/04/Selecting-a-pet-food-for-your-pet-updated-2021_WSAVA-Global-Nutrition-Committee.pdf",
        updated_at="2025-08-12",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "select product", "choose food", "unit price", "tofu litter", "bentonite", "carrier size",
            "collar size", "stainless bowl", "label", "ingredients",
            "chon thuc an", "chon cat ve sinh", "chon san pham", "cat dau nanh", "cat vo cuc", "balo van chuyen", "bat inox", "doc nhan bao bi",
        ),
        summary_vi=(
            "Khi chọn mua đồ dùng thú cưng, hãy đối chiếu đồng thời loài phù hợp, giai đoạn tuổi, đơn giá quy đổi (VND/kg hoặc VND/L) và thông số kỹ thuật trên bao bì."
        ),
        summary_en=(
            "Evaluate pet supplies by verified species compatibility, life-stage labeling, normalized unit cost (per kg or L), and physical sizing on manufacturer labels."
        ),
        bullets_vi=(
            "Thức ăn: kiểm tra rõ công thức dành riêng cho chó hay mèo (mèo cần taurine và đạm động vật đặc thù, không dùng thức ăn chó thay thế lâu dài cho mèo).",
            "Cát vệ sinh: cát đất sét (bentonite) vón cục nhanh và kinh tế theo lít; cát đậu nành (tofu) hạt to hơn, ít bụi mịn và dễ kiểm soát mùi căn hộ.",
            "Phụ kiện (balo, vòng cổ, bát ăn): bát inox 304 dễ vệ sinh hạn chế tích khuẩn cằm mèo; balo/dây dắt cần đo cân nặng và vòng ngực thực tế của bé.",
        ),
        bullets_en=(
            "Nutrition: confirm species-specific formulation—cats have obligate nutritional requirements and should not be fed dog food as a staple diet.",
            "Cat litter: bentonite clay offers tight clumping and low cost per liter, while tofu/soy pellets reduce fine dust for indoor apartments.",
            "Accessories: stainless-steel bowls are hygienic and easy to sanitize; carriers and harnesses must be matched against your pet's actual weight and chest measurements.",
        ),
    ),
    KnowledgeDocument(
        doc_id="KB-VET-009",
        topic="emergency_triage",
        species_scope="both",
        title_vi="Dấu hiệu cấp cứu thú y cần đưa chó mèo đi khám ngay lập tức",
        title_en="Urgent Veterinary Warning Signs Requiring Immediate Evaluation",
        source_name="AVMA 13 Animal Emergencies Requiring Immediate Veterinary Consultation",
        source_url="https://www.avma.org/resources/pet-owners/emergencycare/13-animal-emergencies-requiring-immediate-veterinary-consultation-andor-treatment",
        updated_at="2025-09-10",
        review_status="reviewed",
        version="1.0.0",
        keywords=(
            "emergency", "urgent", "vet", "breathing", "seizure", "blood", "vomit", "lethargy",
            "urinate", "blockage", "poison", "trauma", "bloat",
            "cap cuu", "khan cap", "kham thu y", "kho tho", "co giat", "non ra mau", "bi tieu", "bo an", "ngo doc", "chan thuong",
        ),
        summary_vi=(
            "Các triệu chứng hô hấp, thần kinh, chảy máu, bí tiểu hoặc ngộ độc là tình huống khẩn cấp cần bác sĩ thú y thăm khám trực tiếp ngay lập tức."
        ),
        summary_en=(
            "Respiratory distress, seizures, active bleeding, urinary straining, suspected poisoning, or collapse require immediate in-person veterinary evaluation."
        ),
        bullets_vi=(
            "Đưa đến cơ sở thú y ngay khi thấy: khó thở/há miệng thở gấp (đặc biệt ở mèo), nướu nhợt nhạt hoặc tím tái, co giật, lảo đảo hoặc ngất xỉu.",
            "Cấp cứu tiêu hóa & tiết niệu: nôn hoặc tiêu chảy liên tục/có máu, bụng chướng cứng đau kèm nôn khan, hoặc rặn tiểu nhiều lần không ra nước tiểu.",
            "Không tự ý cho uống thuốc người hay mẹo dân gian tại nhà vì có thể làm nặng thêm tổn thương gan/thận hoặc làm chậm thời gian vàng cấp cứu.",
        ),
        bullets_en=(
            "Seek immediate veterinary care for labored or open-mouth breathing, pale/blue gums, seizures, collapse, or severe trauma.",
            "Urgent GI & urinary signs: repeated vomiting, bloody diarrhea, unproductive retching with a distended abdomen, or straining to urinate without output.",
            "Do not administer home remedies or human medications while delaying professional veterinary care.",
        ),
    ),
)


def _tokenize_with_bigrams(text: str) -> list[str]:
    norm = _normalize(text)
    words = [w for w in re.findall(r"[a-z0-9]+", norm) if len(w) > 1 and w not in _STOPWORDS]
    bigrams = [f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1)]
    return words + bigrams


class BM25KnowledgeRetriever:
    """Lightweight, deterministic Okapi BM25 retriever over reviewed pet-care documents."""

    def __init__(self, documents: tuple[KnowledgeDocument, ...]) -> None:
        self._docs = documents
        self._doc_tokens: list[list[str]] = []
        self._doc_freqs: list[dict[str, int]] = []
        self._df: dict[str, int] = {}

        total_len = 0
        for doc in documents:
            searchable = " ".join((
                doc.topic.replace("_", " "),
                doc.title_vi,
                doc.title_en,
                " ".join(doc.keywords),
                " ".join(doc.keywords),  # 2x field boost for curated topic keywords
                doc.summary_vi,
                doc.summary_en,
                " ".join(doc.bullets_vi),
                " ".join(doc.bullets_en),
            ))
            tokens = _tokenize_with_bigrams(searchable)
            self._doc_tokens.append(tokens)
            total_len += len(tokens)
            tf_map: dict[str, int] = {}
            for tok in tokens:
                tf_map[tok] = tf_map.get(tok, 0) + 1
            self._doc_freqs.append(tf_map)
            for tok in tf_map:
                self._df[tok] = self._df.get(tok, 0) + 1

        self._avgdl = (total_len / len(documents)) if documents else 1.0

    def search(
        self,
        query: str,
        *,
        species_hint: str | None = None,
        top_k: int = 2,
    ) -> list[tuple[KnowledgeDocument, float]]:
        q_tokens = _tokenize_with_bigrams(query)
        if not q_tokens:
            return []
        n_docs = len(self._docs)
        scored: list[tuple[KnowledgeDocument, float]] = []

        for idx, doc in enumerate(self._docs):
            tf_map = self._doc_freqs[idx]
            dl = len(self._doc_tokens[idx])
            score = 0.0
            for term in dict.fromkeys(q_tokens):
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * (dl / self._avgdl))
                score += idf * ((tf * (BM25_K1 + 1.0)) / denom)

            if score > 0 and species_hint in {"cat", "dog"}:
                if doc.species_scope == species_hint:
                    score *= 1.15
                elif doc.species_scope != "both":
                    score *= 0.65

            if score >= MIN_BM25_SCORE:
                scored.append((doc, score))

        scored.sort(key=lambda pair: (-pair[1], pair[0].doc_id))
        return scored[: max(1, min(top_k, 3))]


RETRIEVER = BM25KnowledgeRetriever(KNOWLEDGE_CORPUS)


def standard_vet_disclaimer(locale: str) -> SafetyNotice:
    vi = locale != "en"
    return SafetyNotice(
        severity="disclaimer",
        title="Lưu ý chăm sóc tham khảo (Không thay thế bác sĩ thú y)" if vi else "General Care Guidance (Not Veterinary Advice)",
        message=(
            "PetCare AI cung cấp kiến thức chăm sóc tổng quát từ tài liệu tham khảo đã duyệt, "
            "không phải bác sĩ thú y được cấp phép và không thực hiện chẩn đoán hay kê đơn thuốc."
            if vi else
            "PetCare AI shares general care guidance from reviewed reference material. "
            "It is not a licensed veterinarian and does not diagnose conditions or prescribe medications."
        ),
    )


def build_emergency_triage_response(
    locale: str,
    category: str | None = None,
) -> KnowledgeRetrievalResult:
    """Return high-priority veterinary emergency escalation with cited triage source."""
    vi = locale != "en"
    triage_doc = next(doc for doc in KNOWLEDGE_CORPUS if doc.doc_id == "KB-VET-009")
    poison_doc = next(doc for doc in KNOWLEDGE_CORPUS if doc.doc_id == "KB-SAFE-002")

    if category == "urinary_obstruction":
        msg = (
            "Dấu hiệu rặn nhiều lần trong khay vệ sinh nhưng không ra (hoặc chỉ rỉ vài giọt) nước tiểu — đặc biệt ở mèo đực — có nguy cơ là **tắc nghẽn đường tiết niệu cấp tính** đe dọa tính mạng trong vài giờ. "
            "PetCare AI không chẩn đoán bệnh và không gợi ý mua cát hay sản phẩm thay thế cho việc cấp cứu. Vui lòng đưa thú cưng tới phòng khám/bệnh viện thú y **ngay lập tức**."
            if vi else
            "Repeated straining in the litter box with little or no urine output—especially in male cats—is a classic warning sign of potentially life-threatening **acute urinary obstruction**. "
            "PetCare AI cannot diagnose conditions and will not suggest shopping items in place of urgent care. Please take your pet to an emergency veterinary clinic **immediately**."
        )
    elif category in {"toxin_or_foreign_body_ingestion", "human_medication_toxicity_or_dosing"}:
        msg = (
            "Nghi ngờ thú cưng vừa nuốt chất độc (như xylitol, sô-cô-la, hoa ly, nho khô, bả chuột) hoặc thuốc của người là tình huống **cấp cứu ngộ độc thú y**. "
            "PetCare AI không thể hướng dẫn xử trí giải độc tại nhà. Vui lòng liên hệ và đưa bé tới cơ sở thú y gần nhất **ngay lập tức**."
            if vi else
            "Suspected ingestion of a toxic substance (such as xylitol, chocolate, lilies, raisins/grapes, rodenticide) or human medication is an **urgent veterinary poisoning emergency**. "
            "PetCare AI cannot guide home detoxification. Please contact and transport your pet to an emergency veterinary clinic **immediately**."
        )
    elif category == "acute_neurological_or_jaundice":
        msg = (
            "Dấu hiệu **ấn/tựa đầu vào tường hoặc góc nhà (head-pressing), mất thăng bằng cấp tính, hoặc vàng tròng trắng mắt / nướu / vành tai trong** là cảnh báo thần kinh hoặc chuyển hóa nghiêm trọng. "
            "PetCare AI không chẩn đoán bệnh và không gợi ý sản phẩm thay thế cho việc cấp cứu. Vui lòng đưa thú cưng tới phòng khám/bệnh viện thú y **ngay lập tức**."
            if vi else
            "Signs such as **pressing the head against a wall/corner (head-pressing), acute disorientation, or yellow discoloration of the whites of the eyes, gums, or inner ears** are serious neurological or metabolic red flags. "
            "PetCare AI cannot diagnose conditions and will not suggest shopping items in place of urgent care. Please transport your pet to an emergency veterinary clinic **immediately**."
        )
    elif category == "mucous_membrane_or_shock":
        msg = (
            "Dấu hiệu **nướu/lợi/lưỡi trắng bệch hoặc nhợt nhạt bất thường, hoặc tứ chi/bàn chân lạnh ngắt kèm lừ đừ/mệt lả** là cảnh báo nguy cấp về suy giảm tưới máu, thiếu máu cấp hoặc sốc tuần hoàn. "
            "PetCare AI không thể hướng dẫn xử trí tại nhà; vui lòng ủ ấm nhẹ nhàng và đưa thú cưng tới cơ sở thú y gần nhất **ngay lập tức**."
            if vi else
            "**Very pale or white gums/mucous membranes, or unusually cold extremities paired with weakness or lethargy**, are critical warning signs of poor circulation, severe anemia, or shock. "
            "PetCare AI cannot guide home treatment; keep your pet calm and warm and seek emergency veterinary care **immediately**."
        )
    else:
        msg = (
            "Triệu chứng bạn mô tả là dấu hiệu nguy cấp. PetCare AI không thể chẩn đoán hay hướng dẫn điều trị tại nhà cho tình huống này. "
            "Vui lòng liên hệ và đưa thú cưng tới phòng khám/bệnh viện thú y gần nhất ngay lập tức."
            if vi else
            "The symptoms described are potentially life-threatening warning signs. PetCare AI is not a veterinarian and cannot guide home treatment for emergencies. "
            "Please contact an emergency veterinary clinic immediately."
        )

    notice = SafetyNotice(
        severity="emergency",
        title=(
            "CẢNH BÁO KHẨN CẤP THÚ Y — CẦN ĐƯA ĐI KHÁM NGAY"
            if vi else "URGENT VETERINARY WARNING — SEEK IMMEDIATE CARE"
        ),
        message=msg,
        escalation_steps=(
            (
                "Giữ thú cưng ấm, yên tĩnh, không ấn ép mạnh vào vùng bụng căng và giữ thông thoáng đường thở khi di chuyển tới phòng khám thú y gần nhất.",
                "Nếu nghi ngờ nuốt chất độc, thực phẩm lạ hoặc thuốc của người, mang theo vỏ/nhãn sản phẩm để bác sĩ xác định hoạt chất.",
                "Tuyệt đối không tự ý gây nôn hoặc cho uống thuốc của người khi chưa có chỉ định trực tiếp từ bác sĩ thú y.",
            )
            if vi else
            (
                "Keep your pet calm, warm, avoid pressing on a tense abdomen, and keep the airway unobstructed while transporting to the nearest veterinary clinic.",
                "Bring any suspected toxin packaging, plant sample, or medication container with you.",
                "Do not induce vomiting or give human medications unless explicitly instructed by a licensed veterinarian.",
            )
        ),
    )

    reply = (
        f"{notice.title}: {notice.message}\n"
        + "\n".join(f"• {step}" for step in notice.escalation_steps)
    )
    citations = [
        KnowledgeCitation(
            doc_id=doc.doc_id,
            title=doc.title_vi if vi else doc.title_en,
            source_name=doc.source_name,
            source_url=doc.source_url,
            updated_at=doc.updated_at,
            topic=doc.topic,
            language="vi" if vi else "en",
            review_status=doc.review_status,
            version=doc.version,
            relevance_score=10.0,
        )
        for doc in (triage_doc, poison_doc)
    ]
    return KnowledgeRetrievalResult(
        matched=True,
        reply=reply,
        citations=citations,
        safety_notice=notice,
        follow_up_questions=[],
    )


def build_medical_boundary_response(
    locale: str,
    category: str | None = None,
) -> KnowledgeRetrievalResult:
    """Refuse diagnosis, prescriptions, human OTC medications, and drug dosages clearly and safely."""
    vi = locale != "en"
    triage_doc = next(doc for doc in KNOWLEDGE_CORPUS if doc.doc_id == "KB-VET-009")
    poison_doc = next(doc for doc in KNOWLEDGE_CORPUS if doc.doc_id == "KB-SAFE-002")

    if category == "human_medication_toxicity_or_dosing":
        msg = (
            "**Tuyệt đối không tự ý cho chó mèo dùng thuốc của người** (như paracetamol/Panadol/Tylenol, ibuprofen/Advil, aspirin, hoặc thuốc tiêu chảy người như Smecta, Berberin, Imodium) khi chưa có chỉ định trực tiếp của bác sĩ thú y — nhiều hoạt chất an toàn với người lại gây ngộ độc gan/thận cấp tính hoặc che lấp triệu chứng nguy hiểm ở thú cưng. "
            "PetCare AI không kê đơn hay tính liều thuốc; vui lòng liên hệ bác sĩ thú y để được khám và hướng dẫn an toàn."
            if vi else
            "**Never administer human medications** (such as acetaminophen/Tylenol/paracetamol, ibuprofen/Advil, aspirin, or human antidiarrheals like Smecta, Berberin, or loperamide) to dogs or cats without explicit direction from a licensed veterinarian—several common human drugs can cause severe organ toxicity in pets. "
            "PetCare AI cannot prescribe medications or recommend dosages; please contact a veterinarian promptly for safe evaluation."
        )
        cited_docs = (triage_doc, poison_doc)
    else:
        msg = (
            "PetCare AI không phải bác sĩ thú y được cấp phép nên không chẩn đoán bệnh, không kê đơn kháng sinh/thuốc điều trị "
            "và không tính liều lượng thuốc (mg/kg). Vui lòng đưa bé đến bác sĩ thú y để được khám lâm sàng chính xác."
            if vi else
            "PetCare AI is not a licensed veterinarian and cannot diagnose illnesses, prescribe medications, or recommend drug dosages. "
            "Please consult a licensed veterinarian for clinical examination and safe treatment."
        )
        cited_docs = (triage_doc,)

    notice = SafetyNotice(
        severity="medical_boundary",
        title="Giới hạn an toàn thú y" if vi else "Veterinary Medical Boundary",
        message=msg,
        escalation_steps=(
            (
                "Ghi lại thời điểm xuất hiện triệu chứng, cân nặng, tình trạng ăn uống và đi vệ sinh để cung cấp cho bác sĩ thú y.",
                "Nếu bé đã lỡ uống thuốc của người, hoặc có dấu hiệu lừ đừ nặng, khó thở, nôn/tiêu chảy liên tục hay có máu, hãy đưa đi khám cấp cứu ngay kèm vỏ thuốc.",
            )
            if vi else
            (
                "Note symptom onset, body weight, appetite, water intake, and bathroom changes to share with your veterinarian.",
                "If your pet has already ingested human medication or shows lethargy, labored breathing, repeated vomiting, or bleeding, seek immediate veterinary care with the medication label.",
            )
        ),
    )
    return KnowledgeRetrievalResult(
        matched=False,
        reply=notice.message,
        citations=[
            KnowledgeCitation(
                doc_id=doc.doc_id,
                title=doc.title_vi if vi else doc.title_en,
                source_name=doc.source_name,
                source_url=doc.source_url,
                updated_at=doc.updated_at,
                topic=doc.topic,
                language="vi" if vi else "en",
                review_status=doc.review_status,
                version=doc.version,
                relevance_score=5.0,
            )
            for doc in cited_docs
        ],
        safety_notice=notice,
        follow_up_questions=(
            ["Nguyên tắc chăm sóc vệ sinh cơ bản cho chó mèo", "Thực phẩm trong nhà cần tránh cho thú cưng"]
            if vi else
            ["Basic grooming and hygiene practices for pets", "Which household foods are unsafe for pets?"]
        ),
    )


def answer_from_knowledge_base(
    query: str,
    *,
    species_hint: str | None = None,
    locale: str = "vi",
) -> KnowledgeRetrievalResult:
    """Retrieve reviewed dog/cat care knowledge and compose a grounded cited answer."""
    vi = locale != "en"
    hits = RETRIEVER.search(query, species_hint=species_hint, top_k=2)
    disclaimer = standard_vet_disclaimer(locale)

    # Guard against non-dog/cat exotic species questions even if generic care words matched
    norm = _normalize(query)
    if re.search(
        r"\b(?:iguana|reptiles?|snakes?|turtles?|tortoises?|parrots?|birds?|aquariums?|hamsters?|rabbits?|bunnies|"
        r"sugar\s+gliders?|chinchillas?|hedgehogs?|ferrets?|guinea\s+pigs?|tarantulas?|"
        r"bo\s+sat|ky\s+nhong|nuoi\s+ran|con\s+ran|nuoi\s+rua|rua\s+canh|con\s+rua|chim\s+vet|con\s+vet|nuoi\s+chim|"
        r"ca\s+canh|be\s+ca|chuot\s+hamster|chuot\s+lang|soc\s+bay|nhim\s+kieng|chon\s+suong|tho\s+kieng|nuoi\s+tho)\b",
        norm,
    ):
        hits = []

    if not hits:
        reply = (
            "Kho tri thức đã kiểm duyệt của PetCare AI hiện chỉ bao gồm hướng dẫn chăm sóc tổng quát cho **chó và mèo** "
            "(dinh dưỡng cơ bản, vệ sinh, vận động, chuẩn bị căn hộ, hành vi cơ bản và chọn đồ dùng) và chưa có tài liệu đáng tin cậy cho câu hỏi cụ thể này. "
            "Trợ lý xin phép không tự suy đoán thông tin."
            if vi else
            "PetCare AI's reviewed knowledge base currently covers foundational **dog and cat** care topics "
            "(feeding basics, grooming, enrichment, home preparation, basic behavior, and product selection) and does not contain verified guidance for this specific question. "
            "Rather than guessing, please consult a qualified specialist or veterinarian."
        )
        return KnowledgeRetrievalResult(
            matched=False,
            reply=reply,
            citations=[],
            safety_notice=disclaimer,
            follow_up_questions=(
                [
                    "Cách chuẩn bị căn hộ và khay vệ sinh khi mới đón mèo",
                    "Nguyên tắc cho ăn và chuyển đổi thức ăn trong 7–10 ngày",
                    "Thực phẩm nào trong nhà gây ngộ độc cho chó mèo?",
                ]
                if vi else
                [
                    "How should I prepare my apartment and litter boxes for a new cat?",
                    "How do I safely transition my pet to new food over 7–10 days?",
                    "Which household foods are toxic to dogs and cats?",
                ]
            ),
        )

    primary_doc, _ = hits[0]
    summary = primary_doc.summary_vi if vi else primary_doc.summary_en
    bullets = primary_doc.bullets_vi if vi else primary_doc.bullets_en
    lines = [summary] + [f"• {item}" for item in bullets[:4]]
    if len(hits) > 1:
        sec_doc, _ = hits[1]
        sec_note = sec_doc.summary_vi if vi else sec_doc.summary_en
        lines.append(
            (f"Tham khảo bổ sung ({sec_doc.title_vi}): {sec_note}")
            if vi else (f"Related note ({sec_doc.title_en}): {sec_note}")
        )

    citations = [
        KnowledgeCitation(
            doc_id=doc.doc_id,
            title=doc.title_vi if vi else doc.title_en,
            source_name=doc.source_name,
            source_url=doc.source_url,
            updated_at=doc.updated_at,
            topic=doc.topic,
            language="vi" if vi else "en",
            review_status=doc.review_status,
            version=doc.version,
            relevance_score=score,
        )
        for doc, score in hits
    ]

    follow_ups = (
        [
            "Gợi ý sản phẩm đang còn hàng liên quan đến chủ đề này",
            "Dấu hiệu khẩn cấp nào cần đưa thú cưng đi khám thú y ngay?",
        ]
        if vi else
        [
            "Recommend in-stock products related to this care topic",
            "What urgent warning signs require immediate veterinary care?",
        ]
    )

    return KnowledgeRetrievalResult(
        matched=True,
        reply="\n".join(lines),
        citations=citations,
        safety_notice=disclaimer,
        follow_up_questions=follow_ups,
    )
