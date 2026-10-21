"""Idempotent synthetic demo catalog for isolated local/test databases."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.datastructures import FileStorage

from petcare.config import Config
from petcare.database.connection import read_connection, transaction
from petcare.repositories.base import fetch_all, fetch_one
from petcare.repositories import pet_repo
from petcare.security import hash_password
from petcare.vision.photo_storage import remove_pet_photo, store_pet_photo
from petcare.vision.media_storage import get_media_storage


USERS = (
    ("admin", "Admin@123", "Quản trị cửa hàng", "admin"),
    ("staff1", "Staff@123", "Nhân viên cửa hàng", "staff"),
)

# Phone numbers use an obviously fictional all-zero prefix; these customers are
# for demo and tests only, never imported from a real customer list.
CUSTOMERS = tuple(
    (f"Khách demo {index:02d}", f"00000000{index:02d}", "Dữ liệu mẫu · chưa phải khách thật")
    for index in range(1, 13)
)

# code, name, category, description, price, opening stock, reorder threshold
PRODUCTS = (
    ("FOOD-001", "Thức ăn cho mèo 1kg", "Thức ăn", "Thức ăn hạt cho mèo trưởng thành, túi 1 kg.", 100_000, 10, 5),
    ("ACC-001", "Vòng cổ thú cưng", "Phụ kiện", "Vòng cổ điều chỉnh được, phù hợp mèo và chó nhỏ.", 50_000, 5, 5),
    ("FOOD-002", "Hạt chó vị gà 2kg", "Thức ăn", "Thức ăn khô cho chó trưởng thành, bao 2 kg.", 180_000, 24, 6),
    ("FOOD-003", "Pate mèo cá ngừ 85g", "Thức ăn", "Pate ướt đóng gói một khẩu phần 85 g.", 15_000, 80, 18),
    ("FOOD-004", "Hạt mèo trong nhà 1.5kg", "Thức ăn", "Công thức cho mèo nuôi trong nhà, túi 1.5 kg.", 210_000, 20, 5),
    ("FOOD-005", "Bánh thưởng gà sấy 50g", "Thức ăn", "Bánh thưởng dùng huấn luyện, gói 50 g.", 55_000, 30, 8),
    ("FOOD-006", "Sữa dê cho chó mèo 200ml", "Thức ăn", "Sữa bổ sung cho chó mèo, chai 200 ml.", 32_000, 36, 8),
    ("FOOD-007", "Snack cá hồi cho mèo 40g", "Thức ăn", "Snack cá hồi sấy, gói 40 g.", 48_000, 28, 7),
    ("FOOD-008", "Hạt chó giống nhỏ 1kg", "Thức ăn", "Hạt kích thước nhỏ cho chó trưởng thành giống nhỏ.", 165_000, 24, 6),
    ("CARE-001", "Cát vệ sinh đất sét 10L", "Chăm sóc", "Cát vệ sinh vón cục, bao 10 lít.", 88_000, 40, 8),
    ("CARE-002", "Cát đậu nành 6L", "Chăm sóc", "Cát vệ sinh từ đậu nành, bao 6 lít.", 125_000, 24, 6),
    ("CARE-003", "Sữa tắm yến mạch 250ml", "Chăm sóc", "Sữa tắm dịu nhẹ cho chó mèo, chai 250 ml.", 95_000, 14, 4),
    ("CARE-004", "Khăn ướt thú cưng 80 tờ", "Chăm sóc", "Khăn lau không cồn, gói 80 tờ.", 42_000, 50, 10),
    ("CARE-005", "Dung dịch khử mùi 300ml", "Chăm sóc", "Dung dịch vệ sinh khu vực sinh hoạt, chai 300 ml.", 65_000, 20, 5),
    ("ACC-002", "Bát ăn gốm chống trượt", "Phụ kiện", "Bát gốm nhỏ có đế chống trượt.", 85_000, 18, 4),
    ("ACC-003", "Bộ bát đôi nâng cao", "Phụ kiện", "Giá đỡ hai bát inox cho chó mèo.", 195_000, 10, 3),
    ("ACC-004", "Dây dắt phản quang size M", "Phụ kiện", "Dây dắt có dải phản quang, kích cỡ M.", 145_000, 12, 3),
    ("ACC-005", "Dây dắt nylon 1.5m", "Phụ kiện", "Dây dắt nylon dài 1.5 m, khóa kim loại.", 95_000, 20, 5),
    ("ACC-006", "Ổ nằm thú cưng size S", "Phụ kiện", "Ổ nằm vải mềm có thể tháo giặt, size S.", 320_000, 8, 2),
    ("ACC-007", "Cần câu mèo lông vũ", "Đồ chơi", "Đồ chơi tương tác có cần và lông vũ thay thế.", 35_000, 28, 6),
    ("ACC-008", "Túi vận chuyển lưới", "Phụ kiện", "Túi vận chuyển có lưới thông khí cho thú nhỏ.", 550_000, 6, 2),
    ("ACC-009", "Lược chải lông tự làm sạch", "Chăm sóc", "Lược chải lông có nút đẩy gom lông.", 78_000, 13, 4),
)

# code, name, species, breed, sex, birth date, weight kg, coat, eyes, tags, price
CORE_PETS = (
    ("PET-001", "Miu", "Mèo", "Mèo ta", "female", None, None, "vàng kem", "xanh lá", "lông ngắn, dáng nhỏ", 2_000_000),
    ("PET-002", "Nori", "Mèo", "Mèo ta lông ngắn", "male", "2024-06-12", "3.80", "nâu xám vằn", "hổ phách", "mặt tròn, lông vằn, hiền", 2_400_000),
    ("PET-003", "Mây", "Mèo", "Mèo tam thể", "female", "2025-02-08", "2.80", "trắng cam đen", "xanh lá", "tam thể, lông ngắn, mắt sáng", 2_700_000),
    ("PET-004", "Bơ", "Chó", "Chó lai nhỏ", "male", "2024-09-19", "6.50", "trắng nâu", "nâu", "tai cụp, dáng nhỏ, thân thiện", 3_200_000),
    ("PET-005", "Đốm", "Chó", "Chó ta", "female", "2025-01-14", "8.20", "vàng đốm trắng", "nâu", "lông ngắn, đốm ở ngực", 2_800_000),
    ("PET-006", "Bông", "Thỏ", "Thỏ lông xù", "female", "2025-04-22", "1.40", "trắng", "nâu", "lông dài, tai dựng, dáng nhỏ", 1_500_000),
    ("PET-007", "Mực", "Mèo", "Mèo tuxedo", "male", "2024-12-03", "3.60", "đen trắng", "vàng", "lông ngắn, ngực trắng", 2_500_000),
    ("PET-008", "Milo", "Chó", "Chó lai", "male", "2025-03-11", "4.20", "kem", "nâu", "lông ngắn, mõm nhỏ", 3_000_000),
    ("PET-009", "Mít", "Hamster", "Hamster bear", "unknown", "2025-07-16", "0.12", "vàng trắng", "đen", "lông ngắn, dáng tròn", 350_000),
    ("PET-010", "Sữa", "Mèo", "Mèo ta lông ngắn", "female", "2025-05-27", "2.60", "trắng", "xanh dương", "lông ngắn, mặt sáng", 2_200_000),
)

_DOG_DEMO_ROWS = (
    ("Sunny", "Golden Retriever", "male", "2024-11-05", "28.40", "vàng kim", "nâu", "lông dài, tai cụp, dáng lớn", 12_500_000),
    ("Tít", "Chó lai Terrier", "female", "2025-02-14", "7.20", "trắng nâu", "nâu", "lông ngắn, tai cụp, mảng nâu trên mặt", 4_200_000),
    ("Gấu Mun", "Labrador Retriever", "male", "2025-01-18", "25.60", "đen", "nâu", "lông ngắn, tai cụp, dáng chắc khỏe", 9_800_000),
    ("Kem", "Maltese", "female", "2025-04-20", "3.50", "trắng kem", "đen", "lông dài mềm, dáng nhỏ, mõm ngắn", 6_500_000),
    ("Sói", "German Shepherd", "male", "2024-08-08", "26.00", "nâu đen", "nâu", "tai dựng, mặt nạ đen, dáng lớn", 13_500_000),
    ("Bắp", "Poodle Toy", "female", "2025-03-05", "4.60", "nâu đỏ", "nâu", "lông xoăn, tai cụp, dáng nhỏ", 7_200_000),
    ("Vện", "Chó lai vện", "male", "2024-12-11", "16.50", "nâu vện trắng", "nâu", "lông vện, ngực trắng, tai cụp", 5_800_000),
    ("Mây Gió", "Australian Shepherd", "female", "2024-10-03", "19.80", "đen trắng nâu", "nâu", "tam sắc, lông dài, ngực trắng", 11_800_000),
    ("Bim", "Pug", "male", "2025-05-19", "7.80", "vàng nâu", "nâu", "mõm đen, mặt nhăn, thân hình nhỏ", 6_800_000),
    ("Còi", "Border Collie", "female", "2024-09-15", "18.20", "đen trắng", "nâu", "lông dài, vệt trắng giữa mặt, tai bán dựng", 10_500_000),
    ("Đậu", "Pembroke Welsh Corgi", "male", "2025-01-06", "10.20", "vàng trắng", "nâu", "chân ngắn, tai dựng, ngực trắng", 9_500_000),
    ("Cacao", "Labrador Retriever", "female", "2024-11-25", "22.10", "nâu sô-cô-la", "nâu", "lông ngắn, tai cụp, dáng cân đối", 10_800_000),
    ("Chấm", "Dalmatian", "male", "2025-02-01", "20.20", "trắng đốm đen", "nâu", "lông ngắn, đốm đen toàn thân", 12_000_000),
    ("Kiki", "Yorkshire Terrier", "female", "2025-03-12", "3.10", "vàng nâu xám", "nâu", "lông dài, tai dựng, dáng nhỏ", 7_800_000),
    ("Lạc", "Dachshund", "male", "2024-12-23", "8.80", "đen nâu", "nâu", "thân dài, chân ngắn, tai cụp", 6_900_000),
    ("Bão", "Siberian Husky", "female", "2024-06-02", "21.50", "xám trắng", "xanh dương", "tai dựng, mặt nạ trắng, mắt xanh", 14_500_000),
    ("Hachi", "Shiba Inu", "male", "2025-01-20", "9.60", "vàng đỏ trắng", "nâu", "tai dựng, mõm trắng, đuôi cuộn", 12_800_000),
    ("Momo", "French Bulldog", "female", "2025-04-08", "10.40", "kem", "nâu", "tai lớn dựng, mõm ngắn, lông ngắn", 11_500_000),
    ("Bí", "Beagle", "male", "2025-02-24", "9.20", "tam sắc nâu đen trắng", "nâu", "tai dài cụp, vệt trắng giữa mặt", 8_200_000),
    ("Tuyết", "Samoyed", "female", "2024-09-09", "19.50", "trắng", "nâu", "lông kép dày, tai dựng, dáng lớn", 16_500_000),
    ("Bánh Bao", "Pomeranian", "female", "2025-05-02", "3.20", "cam vàng", "nâu", "lông xù, tai nhỏ dựng, dáng nhỏ", 8_800_000),
    ("Chíp", "Chihuahua", "male", "2025-06-17", "2.60", "vàng nâu", "nâu", "lông ngắn, tai lớn dựng, dáng nhỏ", 5_200_000),
    ("Teddy", "Shih Tzu", "male", "2025-03-29", "5.80", "trắng nâu", "nâu", "lông dài, mặt tròn, tai cụp", 6_900_000),
    ("Rocky", "Rottweiler", "male", "2024-10-21", "31.00", "đen nâu vàng", "nâu", "lông ngắn, mảng vàng trên mặt, dáng lớn", 15_800_000),
    ("Bò Sữa", "English Bulldog", "female", "2025-01-16", "18.00", "vện trắng", "nâu", "mặt nhăn, ngực trắng, thân hình chắc", 13_800_000),
    ("Max", "Great Dane", "male", "2024-12-04", "36.00", "xám xanh", "nâu", "lông ngắn, tai cụp, dáng rất lớn", 18_500_000),
    ("Kuma", "Akita Inu", "male", "2025-02-18", "24.50", "vàng kem trắng", "nâu", "tai dựng, mõm trắng, lông dày", 14_800_000),
    ("Lulu", "Cocker Spaniel", "female", "2025-04-16", "11.60", "vàng mật ong", "nâu", "tai dài phủ lông, lông gợn sóng", 9_200_000),
    ("Mây Con", "Maltese", "female", "2025-06-04", "3.30", "trắng", "đen", "lông dài mượt, mũi đen, dáng nhỏ", 6_800_000),
    ("Mim", "Bichon Frise", "female", "2025-03-21", "5.10", "trắng", "đen", "lông xoăn xù, mặt tròn, dáng nhỏ", 8_500_000),
    ("Pancake", "Pembroke Welsh Corgi", "male", "2025-01-28", "10.80", "vàng trắng", "nâu", "chân ngắn, tai dựng, ngực trắng", 9_800_000),
    ("Rex", "Chó lai đốm", "male", "2024-11-14", "14.20", "nâu trắng đốm", "nâu", "lông ngắn, đốm nâu, tai cụp", 5_900_000),
)

_CAT_DEMO_ROWS = (
    ("Luna", "British Shorthair", "female", "2025-03-14", "4.10", "xám xanh", "hổ phách", "lông ngắn dày, mặt tròn, dáng chắc", 9_500_000),
    ("Miso", "Mèo Xiêm", "male", "2025-01-09", "3.70", "kem nâu sẫm", "xanh dương", "mặt nạ nâu, tai sẫm, mắt xanh", 8_800_000),
    ("Gừng", "Mèo ta lông ngắn", "male", "2025-05-07", "3.20", "cam vằn", "hổ phách", "mướp cam, lông ngắn, tai dựng", 3_200_000),
    ("Tux", "Mèo tuxedo", "male", "2025-02-11", "3.60", "đen trắng", "xanh lá", "lông ngắn, ngực trắng, mặt nạ đen", 3_800_000),
    ("Tam Thể", "Mèo tam thể", "female", "2025-04-02", "3.10", "trắng cam đen", "xanh lá", "tam thể, lông ngắn, mảng màu rõ", 4_200_000),
    ("Bạch Tuyết", "Mèo Ba Tư", "female", "2024-12-18", "4.30", "trắng", "xanh lá", "lông dài, mặt tròn, mũi ngắn", 10_800_000),
    ("Benga", "Mèo Bengal", "male", "2025-01-30", "4.50", "nâu vàng đốm", "vàng", "hoa văn đốm, lông ngắn, dáng thon", 13_500_000),
    ("Bạc", "Mèo Nga xanh", "female", "2025-02-25", "3.40", "xám bạc", "xanh lá", "lông ngắn, màu xám đồng nhất, mắt xanh", 9_800_000),
    ("Simba", "Maine Coon", "male", "2024-10-09", "6.10", "nâu mướp", "vàng", "lông dài dày, tai có túm lông, dáng lớn", 16_500_000),
    ("Nếp", "Mèo Scottish Fold", "female", "2025-05-12", "3.50", "kem", "hổ phách", "tai cụp, mặt tròn, lông ngắn", 11_800_000),
    ("Nhím", "Mèo Sphynx", "male", "2025-03-19", "3.80", "hồng xám", "xanh lá", "ít lông, da có nếp, tai lớn", 15_500_000),
    ("Mơ", "Mèo Ragdoll", "female", "2025-02-07", "4.20", "kem nâu sẫm", "xanh dương", "lông dài, mặt nạ nâu, mắt xanh", 12_500_000),
    ("Muối", "Mèo Mỹ lông ngắn", "female", "2025-01-12", "4.00", "xám bạc vằn", "xanh lá", "lông ngắn, vằn bạc, dáng cân đối", 7_800_000),
    ("Sữa Đậu", "Mèo ta lông ngắn", "female", "2025-06-11", "2.90", "trắng", "xanh lá", "lông ngắn, mắt xanh, tai hồng", 3_500_000),
    ("Đêm", "Mèo đồi mồi", "female", "2025-04-27", "3.30", "đen cam", "vàng", "lông ngắn, hoa văn đồi mồi", 4_100_000),
    ("Mây Xám", "Mèo lông dài lai", "female", "2024-11-19", "4.60", "đen xám", "vàng", "lông dài, đuôi xù, mắt vàng", 5_800_000),
    ("Bạch Kim", "Mèo Turkish Angora", "female", "2025-02-09", "3.60", "trắng", "xanh dương", "lông dài, tai dựng, mắt xanh", 10_500_000),
    ("Mứt", "Mèo Burmese", "male", "2025-01-22", "4.10", "nâu sẫm", "vàng", "lông ngắn bóng, mắt vàng, dáng gọn", 8_700_000),
    ("Gạo", "Mèo Abyssinian", "female", "2025-03-03", "3.40", "nâu đỏ", "vàng", "lông ngắn, màu lông chuyển sắc, dáng thon", 10_200_000),
    ("Tép", "Mèo lai chân ngắn", "male", "2025-06-02", "2.80", "cam trắng", "hổ phách", "lông ngắn, hai màu, dáng thấp", 6_500_000),
    ("Sương", "Mèo rừng Na Uy", "female", "2024-10-16", "5.30", "xám mướp", "xanh lá", "lông dài dày, cổ bờm, tai dựng", 14_800_000),
    ("Hạt Dẻ", "Mèo ta lông dài", "male", "2025-01-27", "4.00", "nâu mướp", "vàng", "lông dài, vằn nâu, đuôi xù", 4_800_000),
    ("Vani", "Mèo ta lông ngắn", "female", "2025-05-18", "3.10", "kem", "hổ phách", "lông ngắn, màu kem đồng nhất", 3_400_000),
    ("Bạc Hà", "Mèo ta lông ngắn", "female", "2025-02-06", "3.50", "bạc mướp", "xanh lá", "lông ngắn, vằn bạc, mắt xanh", 4_000_000),
    ("Cam", "Mèo ta lông dài", "male", "2025-04-24", "4.10", "cam trắng", "hổ phách", "lông dài, ngực trắng, đuôi xù", 4_700_000),
    ("Bọt", "Mèo lai lông ngắn", "female", "2025-06-07", "2.90", "xám trắng", "xanh lá", "lông ngắn, ngực trắng, mặt xám", 3_600_000),
    ("Leo", "Mèo Bengal", "male", "2025-01-13", "4.80", "vàng nâu đốm", "xanh lá", "hoa văn đốm, lông ngắn, dáng thể thao", 14_200_000),
    ("Chanh", "Mèo lai lông ngắn", "male", "2025-03-08", "3.40", "xám trắng", "xanh lá", "lông ngắn, mặt nạ xám, ngực trắng", 3_900_000),
    ("Yuki", "Mèo Xiêm", "female", "2025-02-20", "3.60", "kem nâu sô-cô-la", "xanh dương", "mặt nạ sẫm, tai lớn, mắt xanh", 9_200_000),
    ("Latte", "Mèo Ba Tư", "female", "2024-12-30", "4.50", "xám khói", "hổ phách", "lông dài dày, mặt tròn, mũi ngắn", 11_200_000),
    ("Panda", "Mèo tuxedo", "male", "2025-05-24", "3.30", "đen trắng", "xanh lá", "lông ngắn, ngực trắng, mặt nạ đen", 3_800_000),
    ("Sọc", "Mèo ta lông ngắn", "male", "2025-04-12", "3.60", "nâu trắng mướp", "vàng", "lông ngắn, vằn nâu, ngực trắng", 3_700_000),
)

ADDITIONAL_DEMO_PETS = tuple(
    (f"PET-{index:03d}", name, "Chó", breed, sex, birth_date, weight, coat, eyes, tags, price)
    for index, (name, breed, sex, birth_date, weight, coat, eyes, tags, price)
    in enumerate(_DOG_DEMO_ROWS, start=101)
) + tuple(
    (f"PET-{index:03d}", name, "Mèo", breed, sex, birth_date, weight, coat, eyes, tags, price)
    for index, (name, breed, sex, birth_date, weight, coat, eyes, tags, price)
    in enumerate(_CAT_DEMO_ROWS, start=133)
)

PETS = CORE_PETS + ADDITIONAL_DEMO_PETS

DEMO_PET_IMAGES = {
    "PET-001": "miu-orange-cream.png",
    "PET-002": "nori-tabby.png",
    "PET-003": "may-calico.png",
    "PET-004": "bo-mixed-dog.png",
    **{f"PET-{100 + index:03d}": f"demo-dog-{index:02d}.png" for index in range(1, 33)},
    **{f"PET-{132 + index:03d}": f"demo-cat-{index:02d}.png" for index in range(1, 33)},
}

# marker, days ago, customer index, product code/quantity lines
DEMO_SALES = (
    ("DEMO-SALE-01", 0, 0, (("FOOD-003", 2), ("CARE-001", 1))),
    ("DEMO-SALE-02", 3, 1, (("FOOD-002", 1), ("ACC-007", 1))),
    ("DEMO-SALE-03", 7, 2, (("FOOD-004", 1), ("ACC-002", 1))),
    ("DEMO-SALE-04", 12, 3, (("CARE-003", 2), ("ACC-005", 1))),
    ("DEMO-SALE-05", 20, 4, (("FOOD-008", 2), ("ACC-009", 1))),
    ("DEMO-SALE-06", 40, 5, (("CARE-002", 1), ("ACC-006", 1))),
    ("DEMO-SALE-07", 65, 6, (("FOOD-007", 2), ("CARE-005", 1))),
)

DEMO_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "demo" / "pets"


def seed_database():
    """Add demo rows without replacing data already maintained by the user."""
    created_photos = []
    pet_media_storage = get_media_storage(Config, "pets")
    try:
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT id FROM tenants WHERE slug = 'main' AND status = 'active'")
                tenant_id = cursor.fetchone()[0]
                cursor.execute("SET @petcare_tenant_id = %s", (tenant_id,))
                for username, password, full_name, role in USERS:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, full_name, role) "
                        "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE username = VALUES(username)",
                        (username, hash_password(password), full_name, role),
                    )
                    cursor.execute(
                        "INSERT INTO tenant_users (tenant_id, user_id, role, active) "
                        "SELECT %s, id, %s, active FROM users WHERE username = %s "
                        "ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)",
                        (tenant_id, "owner" if role == "admin" else "staff", username),
                    )

                for full_name, phone, address in CUSTOMERS:
                    cursor.execute(
                        "INSERT INTO customers (tenant_id, full_name, phone, address) "
                        "SELECT %s, %s, %s, %s WHERE NOT EXISTS "
                        "(SELECT 1 FROM customers WHERE tenant_id = %s AND phone = %s)",
                        (tenant_id, full_name, phone, address, tenant_id, phone),
                    )

                for code, name, category, description, price, stock, reorder_level in PRODUCTS:
                    cursor.execute(
                        "INSERT INTO products "
                        "(tenant_id, code, name, category, description, unit_price, unit_price_vnd, stock_qty, reorder_level) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE code = VALUES(code)",
                        (tenant_id, code, name, category, description, price, price, stock, reorder_level),
                    )
                    cursor.execute("SELECT id FROM products WHERE tenant_id = %s AND code = %s", (tenant_id, code))
                    product_id = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT 1 FROM stock_movements WHERE tenant_id = %s AND product_id = %s LIMIT 1",
                        (tenant_id, product_id),
                    )
                    if cursor.fetchone() is None:
                        cursor.execute(
                            "INSERT INTO stock_movements "
                            "(tenant_id, product_id, quantity_delta, reason, created_by) "
                            "SELECT %s, p.id, p.stock_qty, 'Tồn đầu kỳ dữ liệu demo', u.id "
                            "FROM products p CROSS JOIN users u "
                            "WHERE p.id = %s AND p.tenant_id = %s AND p.stock_qty > 0 "
                            "AND u.username = 'admin'",
                            (tenant_id, product_id, tenant_id),
                        )

                for pet in PETS:
                    (code, name, species, breed, sex, birth_date, weight, coat_color,
                     eye_color, appearance_tags, price) = pet
                    cursor.execute(
                        "SELECT id, photo_filename FROM pets WHERE tenant_id = %s AND code = %s",
                        (tenant_id, code),
                    )
                    existed_before_seed = cursor.fetchone() is not None
                    cursor.execute(
                        "INSERT INTO pets "
                        "(tenant_id, code, name, species, breed, sex, birth_date, weight_kg, coat_color, "
                        "eye_color, appearance_tags, sale_price, sale_price_vnd) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE code = VALUES(code)",
                        (tenant_id, *pet, price),
                    )
                    filename = DEMO_PET_IMAGES.get(code)
                    source = DEMO_ASSET_DIR / filename if filename else None
                    if not existed_before_seed and source and source.is_file():
                        with source.open("rb") as stream:
                            stored = store_pet_photo(
                                FileStorage(stream=stream, filename=source.name),
                                pet_media_storage,
                                Config.PET_IMAGE_MAX_BYTES,
                                tenant_id=tenant_id,
                            )
                        created_photos.append(stored.filename)
                        cursor.execute(
                            "UPDATE pets SET photo_filename = %s, photo_descriptor = %s "
                            "WHERE tenant_id = %s AND code = %s AND photo_filename IS NULL",
                            (stored.filename, stored.descriptor_json, tenant_id, code),
                        )
                        if cursor.rowcount:
                            cursor.execute(
                                "SELECT id FROM pets WHERE tenant_id = %s AND code = %s",
                                (tenant_id, code),
                            )
                            pet_id = cursor.fetchone()[0]
                            pet_repo.replace_photo_search_index(
                                connection, tenant_id, pet_id, stored.descriptor_json
                            )
            finally:
                cursor.close()
    except Exception:
        for filename in created_photos:
            remove_pet_photo(filename, pet_media_storage)
        raise

    _seed_demo_sales()


def _seed_demo_sales():
    from petcare.services import invoice_service

    with read_connection() as connection:
        tenant = fetch_one(connection, "SELECT id FROM tenants WHERE slug = 'main'")
        admin = fetch_one(
            connection,
            "SELECT u.id FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
            "JOIN tenants t ON t.id = tu.tenant_id WHERE u.username = 'admin' "
            "AND t.slug = 'main' AND tu.active = 1 "
            "AND (SELECT COUNT(*) FROM tenant_users x WHERE x.user_id = u.id AND x.active = 1) = 1",
        )
        customers = {
            row["phone"]: row["id"]
            for row in fetch_all(
                connection,
                "SELECT c.id, c.phone FROM customers c JOIN tenants t ON t.id = c.tenant_id "
                "WHERE t.slug = 'main' AND c.phone IN (" +
                ",".join(["%s"] * len(CUSTOMERS)) + ")",
                tuple(customer[1] for customer in CUSTOMERS),
            )
        }
        products = {
            row["code"]: row["id"]
            for row in fetch_all(
                connection,
                "SELECT p.id, p.code FROM products p JOIN tenants t ON t.id = p.tenant_id "
                "WHERE t.slug = 'main' AND p.code IN (" +
                ",".join(["%s"] * len(PRODUCTS)) + ")",
                tuple(product[0] for product in PRODUCTS),
            )
        }
        existing = {
            row["note"]: (row["id"], row["status"])
            for row in fetch_all(
                connection,
                "SELECT i.id, i.note, i.status FROM invoices i JOIN tenants t ON t.id = i.tenant_id "
                "WHERE t.slug = 'main' AND i.note LIKE '[DEMO] DEMO-SALE-%'",
            )
        }

    if not admin or not tenant:
        return
    for marker, days_ago, customer_index, lines in DEMO_SALES:
        note = f"[DEMO] {marker} · dữ liệu giao dịch mẫu"
        existing_invoice = existing.get(note)
        if existing_invoice and existing_invoice[1] != "unpaid":
            continue
        if existing_invoice:
            invoice_id = existing_invoice[0]
        else:
            customer = CUSTOMERS[customer_index]
            customer_id = customers.get(customer[1])
            if not customer_id or any(code not in products for code, _quantity in lines):
                continue
            invoice_id = invoice_service.create_invoice(
                admin["id"],
                {"customer_id": str(customer_id), "note": note},
                [
                    {"item_type": "product", "item_id": str(products[code]), "quantity": str(quantity)}
                    for code, quantity in lines
                ],
            )
        invoice_service.pay_invoice(admin["id"], invoice_id)
        paid_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (tenant["id"],))
                cursor.execute(
                    "UPDATE invoices SET created_at = %s, paid_at = %s "
                    "WHERE id = %s AND tenant_id = @petcare_tenant_id "
                    "AND status = 'paid' AND note = %s",
                    (paid_at, paid_at, invoice_id, note),
                )
            finally:
                cursor.close()

    with transaction() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SET @petcare_tenant_id = %s", (tenant["id"],))
            cursor.execute(
                "UPDATE stock_movements sm JOIN invoices i ON i.id = sm.invoice_id "
                "AND i.tenant_id = sm.tenant_id "
                "SET sm.created_at = i.paid_at "
                "WHERE i.tenant_id = @petcare_tenant_id AND sm.tenant_id = @petcare_tenant_id "
                "AND i.status = 'paid' AND i.note LIKE '[DEMO] DEMO-SALE-%'"
            )
        finally:
            cursor.close()


if __name__ == "__main__":
    if not Config.DB_NAME.endswith(("_dev", "_test")):
        raise SystemExit(
            "Từ chối nạp dữ liệu demo vào database không có hậu tố _dev hoặc _test."
        )
    seed_database()
    print("Đã nạp dữ liệu demo tổng hợp, ảnh mẫu và giao dịch mẫu idempotent.")
