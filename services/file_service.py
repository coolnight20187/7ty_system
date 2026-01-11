import os
import shutil
import zipfile
import csv
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, BinaryIO, Union
from datetime import datetime, date
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
import magic
from PIL import Image
import io
import json

from database import get_db
from models import FileUpload, User, Bill, Agent, Customer, BillStatus
from schemas import FileUploadResponse, ImportResponse
from config import settings
from utils import (
    generate_bill_code,
    generate_unique_filename,
    validate_file_type,
    calculate_file_hash
)

class FileService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_FOLDER)
        self.max_file_size = settings.MAX_UPLOAD_SIZE
        self.allowed_mime_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'document': ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            'archive': ['application/zip', 'application/x-zip-compressed'],
            'csv': ['text/csv', 'application/csv'],
            'json': ['application/json']
        }
        
        # Tạo thư mục upload nếu chưa tồn tại
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Tạo các thư mục con
        self.ensure_subdirectories()

    def ensure_subdirectories(self):
        """Tạo các thư mục con cần thiết"""
        subdirs = [
            'avatars',
            'bills',
            'exports',
            'backups',
            'templates',
            'temp'
        ]
        
        for subdir in subdirs:
            (self.upload_dir / subdir).mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile, allowed_types: List[str] = None) -> Tuple[bool, str]:
        """
        Kiểm tra file upload
        """
        try:
            # Kiểm tra kích thước file
            file.file.seek(0, 2)  # Di chuyển đến cuối file
            file_size = file.file.tell()
            file.file.seek(0)  # Trở lại đầu file
            
            if file_size > self.max_file_size:
                return False, f"File quá lớn. Kích thước tối đa: {self.max_file_size // (1024*1024)}MB"
            
            # Đọc phần đầu file để xác định loại MIME
            file_content = file.file.read(1024)
            file.file.seek(0)
            
            mime_type = magic.from_buffer(file_content, mime=True)
            
            if allowed_types:
                if mime_type not in allowed_types:
                    return False, f"Loại file không được hỗ trợ. Chấp nhận: {', '.join(allowed_types)}"
            else:
                # Kiểm tra tất cả các loại được phép
                allowed_all = []
                for types in self.allowed_mime_types.values():
                    allowed_all.extend(types)
                
                if mime_type not in allowed_all:
                    return False, "Loại file không được hỗ trợ"
            
            # Kiểm tra phần mở rộng file
            filename = file.filename.lower()
            if filename.endswith(('.php', '.exe', '.sh', '.bat', '.cmd')):
                return False, "File thực thi không được phép upload"
            
            return True, "File hợp lệ"
            
        except Exception as e:
            return False, f"Lỗi kiểm tra file: {str(e)}"

    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: int,
        upload_type: str = "general",
        subdirectory: str = "",
        db: Session = None
    ) -> FileUploadResponse:
        """
        Upload file lên server
        """
        try:
            # Xác định loại file được phép
            allowed_types = []
            if upload_type == "avatar":
                allowed_types = self.allowed_mime_types['image']
                subdirectory = "avatars"
            elif upload_type == "bill_import":
                allowed_types = self.allowed_mime_types['csv'] + self.allowed_mime_types['document']
                subdirectory = "bills"
            elif upload_type == "backup":
                allowed_types = self.allowed_mime_types['archive'] + self.allowed_mime_types['document']
                subdirectory = "backups"
            elif upload_type == "template":
                allowed_types = self.allowed_mime_types['document'] + self.allowed_mime_types['csv']
                subdirectory = "templates"
            else:
                allowed_types = sum(self.allowed_mime_types.values(), [])  # Tất cả các loại
            
            # Kiểm tra file
            is_valid, message = self.validate_file(file, allowed_types)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
            
            # Tạo tên file duy nhất
            original_filename = file.filename
            file_extension = Path(original_filename).suffix
            unique_filename = generate_unique_filename(file_extension)
            
            # Tạo đường dẫn lưu file
            save_dir = self.upload_dir / subdirectory
            save_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = save_dir / unique_filename
            
            # Lưu file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Tính toán file hash
            file_hash = calculate_file_hash(file_path)
            
            # Lấy thông tin file
            file_size = os.path.getsize(file_path)
            mime_type = magic.from_file(file_path, mime=True)
            
            # Lưu thông tin vào database
            db_file = FileUpload(
                filename=unique_filename,
                original_filename=original_filename,
                file_path=str(file_path),
                file_size=file_size,
                mime_type=mime_type,
                upload_type=upload_type,
                user_id=user_id,
                status="completed",
                metadata={
                    "uploaded_at": datetime.now().isoformat(),
                    "original_name": original_filename,
                    "file_hash": file_hash
                }
            )
            
            if db:
                db.add(db_file)
                db.commit()
                db.refresh(db_file)
            
            return FileUploadResponse(
                id=db_file.id if db else 0,
                filename=unique_filename,
                original_filename=original_filename,
                file_path=str(file_path),
                file_size=file_size,
                mime_type=mime_type,
                upload_type=upload_type,
                user_id=user_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="completed",
                processed_at=None,
                processed_count=0,
                error_count=0,
                error_log=None
            )
            
        except HTTPException:
            raise
        except Exception as e:
            if db:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi upload file: {str(e)}"
            )

    async def process_bill_import(
        self, 
        file_path: str, 
        user_id: int,
        agent_id: Optional[int] = None,
        override: bool = False,
        db: Session = None
    ) -> ImportResponse:
        """
        Xử lý import file hóa đơn (Excel/CSV)
        """
        try:
            imported_count = 0
            skipped_count = 0
            errors = []
            bill_codes = []
            
            # Đọc file dựa trên định dạng
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, dtype=str)
            elif file_ext == '.csv':
                df = pd.read_csv(file_path, dtype=str, encoding='utf-8')
            else:
                return ImportResponse(
                    success=False,
                    message="Định dạng file không được hỗ trợ",
                    imported_count=0,
                    skipped_count=0,
                    errors=["Chỉ hỗ trợ file Excel (.xlsx, .xls) hoặc CSV (.csv)"],
                    file_path=file_path
                )
            
            # Chuẩn hóa tên cột (bỏ khoảng trắng, lowercase)
            df.columns = df.columns.str.strip().str.lower()
            
            # Map các cột bắt buộc
            column_mapping = {
                'customer_code': ['ma_kh', 'customer_code', 'ma_khach_hang'],
                'customer_name': ['ten_kh', 'customer_name', 'ten_khach_hang'],
                'period': ['ky', 'period', 'ky_thanh_toan'],
                'total_amount': ['tong_tien', 'total_amount', 'tien'],
                'electricity_amount': ['tien_dien', 'electricity_amount']
            }
            
            # Tìm cột thực tế dựa trên mapping
            actual_columns = {}
            for standard_col, possible_cols in column_mapping.items():
                found = False
                for col in possible_cols:
                    if col in df.columns:
                        actual_columns[standard_col] = col
                        found = True
                        break
                if not found and standard_col in ['customer_code', 'customer_name', 'period', 'total_amount']:
                    errors.append(f"Thiếu cột bắt buộc: {standard_col}")
                    return ImportResponse(
                        success=False,
                        message="Thiếu cột bắt buộc",
                        imported_count=0,
                        skipped_count=0,
                        errors=errors,
                        file_path=file_path
                    )
            
            # Xử lý từng dòng
            for index, row in df.iterrows():
                try:
                    # Lấy giá trị từ các cột
                    customer_code = str(row[actual_columns['customer_code']]).strip()
                    customer_name = str(row[actual_columns['customer_name']]).strip()
                    period = str(row[actual_columns['period']]).strip()
                    total_amount = float(str(row[actual_columns['total_amount']]).replace(',', ''))
                    
                    # Kiểm tra dữ liệu
                    if not customer_code or not customer_name or not period:
                        errors.append(f"Dòng {index + 2}: Thiếu thông tin bắt buộc")
                        skipped_count += 1
                        continue
                    
                    # Kiểm tra định dạng period (YYYY-MM)
                    try:
                        datetime.strptime(period, "%Y-%m")
                    except ValueError:
                        errors.append(f"Dòng {index + 2}: Kỳ thanh toán không đúng định dạng (YYYY-MM)")
                        skipped_count += 1
                        continue
                    
                    # Kiểm tra số tiền
                    if total_amount <= 0:
                        errors.append(f"Dòng {index + 2}: Số tiền phải lớn hơn 0")
                        skipped_count += 1
                        continue
                    
                    # Kiểm tra hóa đơn đã tồn tại
                    existing_bill = db.query(Bill).filter(
                        Bill.customer_code == customer_code,
                        Bill.period == period
                    ).first()
                    
                    if existing_bill:
                        if override:
                            # Cập nhật hóa đơn cũ
                            existing_bill.total_amount = total_amount
                            existing_bill.customer_name = customer_name
                            
                            # Cập nhật các trường tùy chọn nếu có
                            for optional_col in ['electricity_amount', 'vat_amount', 'other_fees', 
                                               'consumption', 'previous_index', 'current_index']:
                                if optional_col in actual_columns:
                                    value = str(row[actual_columns[optional_col]]).strip()
                                    if value:
                                        try:
                                            setattr(existing_bill, optional_col, float(value))
                                        except (ValueError, TypeError):
                                            pass
                            
                            existing_bill.updated_at = datetime.now()
                            imported_count += 1
                            bill_codes.append(existing_bill.bill_code)
                        else:
                            errors.append(f"Dòng {index + 2}: Hóa đơn đã tồn tại (Mã KH: {customer_code}, Kỳ: {period})")
                            skipped_count += 1
                        continue
                    
                    # Tạo hóa đơn mới
                    bill_code = generate_bill_code()
                    
                    new_bill = Bill(
                        bill_code=bill_code,
                        customer_code=customer_code,
                        customer_name=customer_name,
                        period=period,
                        total_amount=total_amount,
                        status=BillStatus.IN_STOCK,
                        created_by_id=user_id,
                        agent_id=agent_id
                    )
                    
                    # Cập nhật các trường tùy chọn
                    electricity_amount = None
                    if 'electricity_amount' in actual_columns:
                        try:
                            electricity_amount = float(str(row[actual_columns['electricity_amount']]).replace(',', ''))
                            new_bill.electricity_amount = electricity_amount
                        except (ValueError, TypeError):
                            pass
                    
                    # Các trường khác
                    optional_fields = {
                        'customer_address': ['dia_chi', 'address'],
                        'customer_phone': ['dien_thoai', 'phone'],
                        'due_date': ['han_thanh_toan', 'due_date'],
                        'consumption': ['san_luong', 'consumption'],
                        'previous_index': ['chi_so_cu', 'previous_index'],
                        'current_index': ['chi_so_moi', 'current_index'],
                        'notes': ['ghi_chu', 'notes']
                    }
                    
                    for field, possible_cols in optional_fields.items():
                        for col in possible_cols:
                            if col in df.columns:
                                value = str(row[col]).strip()
                                if value and value.lower() not in ['nan', 'null', 'none', '']:
                                    if field == 'due_date':
                                        try:
                                            # Thử parse nhiều định dạng ngày
                                            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                                                try:
                                                    date_value = datetime.strptime(value, fmt).date()
                                                    setattr(new_bill, field, date_value)
                                                    break
                                                except ValueError:
                                                    continue
                                        except ValueError:
                                            pass
                                    elif field in ['consumption', 'previous_index', 'current_index']:
                                        try:
                                            setattr(new_bill, field, float(value.replace(',', '')))
                                        except (ValueError, TypeError):
                                            pass
                                    else:
                                        setattr(new_bill, field, value)
                                    break
                    
                    db.add(new_bill)
                    imported_count += 1
                    bill_codes.append(bill_code)
                    
                except Exception as e:
                    errors.append(f"Dòng {index + 2}: {str(e)}")
                    skipped_count += 1
                    continue
            
            # Commit transaction
            if db and imported_count > 0:
                db.commit()
            
            # Cập nhật trạng thái file upload
            if db:
                file_upload = db.query(FileUpload).filter(
                    FileUpload.file_path == file_path
                ).first()
                
                if file_upload:
                    file_upload.status = "processed"
                    file_upload.processed_at = datetime.now()
                    file_upload.processed_count = imported_count
                    file_upload.error_count = skipped_count
                    file_upload.error_log = json.dumps(errors) if errors else None
                    db.commit()
            
            return ImportResponse(
                success=True,
                message=f"Đã import {imported_count} hóa đơn, bỏ qua {skipped_count}",
                imported_count=imported_count,
                skipped_count=skipped_count,
                errors=errors[:10],  # Chỉ trả về 10 lỗi đầu tiên
                file_path=file_path
            )
            
        except Exception as e:
            if db:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xử lý file import: {str(e)}"
            )

    async def export_data(
        self,
        data: List[Dict[str, Any]],
        filename: str,
        format: str = "excel",
        include_headers: bool = True
    ) -> str:
        """
        Xuất dữ liệu ra file Excel/CSV
        """
        try:
            # Tạo DataFrame từ dữ liệu
            df = pd.DataFrame(data)
            
            # Tạo tên file đầy đủ
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_filename = f"{filename}_{timestamp}"
            
            # Xác định thư mục lưu
            export_dir = self.upload_dir / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Xuất file theo định dạng
            if format == "excel":
                file_path = export_dir / f"{full_filename}.xlsx"
                
                # Tạo Excel writer với engine xlsxwriter
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Data', index=False, header=include_headers)
                    
                    # Định dạng workbook
                    workbook = writer.book
                    worksheet = writer.sheets['Data']
                    
                    # Định dạng header
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BD',
                        'border': 1
                    })
                    
                    # Định dạng cell số
                    number_format = workbook.add_format({'num_format': '#,##0'})
                    
                    # Định dạng cell ngày
                    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                    
                    # Áp dụng định dạng
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Tự động điều chỉnh độ rộng cột
                    for i, col in enumerate(df.columns):
                        column_len = max(
                            df[col].astype(str).str.len().max(),
                            len(str(col))
                        ) + 2
                        worksheet.set_column(i, i, min(column_len, 50))
                        
            elif format == "csv":
                file_path = export_dir / f"{full_filename}.csv"
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            else:
                raise ValueError(f"Định dạng {format} không được hỗ trợ")
            
            return str(file_path)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xuất dữ liệu: {str(e)}"
            )

    async def generate_template(self, template_type: str) -> str:
        """
        Tạo file template cho import
        """
        try:
            template_dir = self.upload_dir / "templates"
            template_dir.mkdir(parents=True, exist_ok=True)
            
            if template_type == "bills":
                # Template import hóa đơn
                data = [
                    {
                        "ma_kh": "KH001",
                        "ten_kh": "Nguyễn Văn A",
                        "dia_chi": "123 Đường ABC",
                        "dien_thoai": "0901234567",
                        "ky": "2024-01",
                        "han_thanh_toan": "2024-01-15",
                        "tong_tien": "1500000",
                        "tien_dien": "1200000",
                        "vat": "150000",
                        "phi_khac": "150000",
                        "san_luong": "350",
                        "chi_so_cu": "12345",
                        "chi_so_moi": "12695",
                        "ghi_chu": "Hóa đơn tháng 1"
                    }
                ]
                
                df = pd.DataFrame(data)
                file_path = template_dir / "template_import_hoa_don.xlsx"
                
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Mẫu', index=False)
                    
                    # Thêm sheet hướng dẫn
                    instructions = [
                        ["HƯỚNG DẪN NHẬP LIỆU"],
                        [""],
                        ["1. Các cột bắt buộc: ma_kh, ten_kh, ky, tong_tien"],
                        ["2. Định dạng kỳ: YYYY-MM (ví dụ: 2024-01)"],
                        ["3. Định dạng ngày: YYYY-MM-DD"],
                        ["4. Số tiền: chỉ nhập số, không có dấu phẩy"],
                        ["5. Mã KH không được trùng trong cùng kỳ"],
                        [""],
                        ["CỘT", "MÔ TẢ", "VÍ DỤ"],
                        ["ma_kh", "Mã khách hàng", "KH001"],
                        ["ten_kh", "Tên khách hàng", "Nguyễn Văn A"],
                        ["dia_chi", "Địa chỉ", "123 Đường ABC"],
                        ["dien_thoai", "Điện thoại", "0901234567"],
                        ["ky", "Kỳ thanh toán", "2024-01"],
                        ["han_thanh_toan", "Hạn thanh toán", "2024-01-15"],
                        ["tong_tien", "Tổng tiền", "1500000"],
                        ["tien_dien", "Tiền điện", "1200000"],
                        ["vat", "VAT", "150000"],
                        ["phi_khac", "Phí khác", "150000"],
                        ["san_luong", "Sản lượng (kWh)", "350"],
                        ["chi_so_cu", "Chỉ số cũ", "12345"],
                        ["chi_so_moi", "Chỉ số mới", "12695"],
                        ["ghi_chu", "Ghi chú", "Hóa đơn tháng 1"]
                    ]
                    
                    df_instructions = pd.DataFrame(instructions[8:], columns=instructions[7])
                    df_instructions.to_excel(writer, sheet_name='Hướng dẫn', index=False)
                    
                    # Định dạng
                    workbook = writer.book
                    worksheet = writer.sheets['Hướng dẫn']
                    
                    # Merge cells cho tiêu đề
                    merge_format = workbook.add_format({
                        'bold': True,
                        'align': 'center',
                        'valign': 'vcenter',
                        'font_size': 14
                    })
                    
                    for i, instruction in enumerate(instructions[:7]):
                        worksheet.merge_range(i, 0, i, 2, instruction[0], merge_format)
            
            elif template_type == "agents":
                # Template import đại lý
                data = [
                    {
                        "ma_dai_ly": "DL001",
                        "ten_dai_ly": "Nguyễn Văn B",
                        "ten_cong_ty": "Công ty TNHH ABC",
                        "ma_so_thue": "0123456789",
                        "dien_thoai": "0909876543",
                        "email": "agent@example.com",
                        "dia_chi": "456 Đường XYZ",
                        "loai_dai_ly": "cá nhân",
                        "ty_le_hoa_hong": "1.5"
                    }
                ]
                
                df = pd.DataFrame(data)
                file_path = template_dir / "template_import_dai_ly.xlsx"
                df.to_excel(file_path, index=False)
            
            elif template_type == "customers":
                # Template import khách hàng
                data = [
                    {
                        "ma_kh": "KH001",
                        "ten_kh": "Nguyễn Văn C",
                        "dien_thoai": "0912345678",
                        "email": "customer@example.com",
                        "dia_chi": "789 Đường DEF",
                        "ma_kh_evn": "EVN001",
                        "ma_cong_to": "CT001",
                        "ma_hop_dong": "HD001",
                        "cap_dien_ap": "220V",
                        "loai_dien": "sinh hoạt"
                    }
                ]
                
                df = pd.DataFrame(data)
                file_path = template_dir / "template_import_khach_hang.xlsx"
                df.to_excel(file_path, index=False)
            
            else:
                raise ValueError(f"Loại template {template_type} không được hỗ trợ")
            
            return str(file_path)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi tạo template: {str(e)}"
            )

    async def process_avatar(self, file_path: str, user_id: int) -> str:
        """
        Xử lý ảnh đại diện: resize và tối ưu hóa
        """
        try:
            # Kiểm tra file tồn tại
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File không tồn tại: {file_path}")
            
            # Mở ảnh
            with Image.open(file_path) as img:
                # Chuyển sang RGB nếu cần
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Resize ảnh
                max_size = (300, 300)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Tạo tên file mới
                new_filename = f"avatar_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                new_file_path = self.upload_dir / "avatars" / new_filename
                
                # Lưu ảnh đã tối ưu
                img.save(new_file_path, 'JPEG', quality=85, optimize=True)
                
                # Xóa file gốc
                os.remove(file_path)
                
                return str(new_file_path)
                
        except Exception as e:
            # Nếu xử lý thất bại, giữ nguyên file gốc
            return file_path

    async def compress_files(self, file_paths: List[str], output_filename: str) -> str:
        """
        Nén nhiều file thành file zip
        """
        try:
            output_dir = self.upload_dir / "exports"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            zip_path = output_dir / f"{output_filename}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        arcname = os.path.basename(file_path)
                        zipf.write(file_path, arcname)
            
            return str(zip_path)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi nén file: {str(e)}"
            )

    async def extract_archive(self, file_path: str, extract_to: str = None) -> List[str]:
        """
        Giải nén file archive
        """
        try:
            if extract_to is None:
                extract_to = self.upload_dir / "temp" / Path(file_path).stem
                extract_to.mkdir(parents=True, exist_ok=True)
            
            extracted_files = []
            
            with zipfile.ZipFile(file_path, 'r') as zipf:
                # Kiểm tra file độc hại
                for member in zipf.namelist():
                    if member.startswith('/') or '..' in member:
                        raise ValueError(f"File archive chứa đường dẫn không an toàn: {member}")
                    
                    if member.lower().endswith(('.exe', '.bat', '.sh', '.php')):
                        raise ValueError(f"File archive chứa file thực thi: {member}")
                
                # Giải nén
                zipf.extractall(extract_to)
                extracted_files = zipf.namelist()
            
            # Tạo danh sách đường dẫn đầy đủ
            full_paths = [str(Path(extract_to) / f) for f in extracted_files]
            
            return full_paths
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi giải nén file: {str(e)}"
            )

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Lấy thông tin chi tiết về file
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File không tồn tại: {file_path}")
            
            stat_info = os.stat(file_path)
            mime_type = magic.from_file(file_path, mime=True)
            
            return {
                "path": file_path,
                "size": stat_info.st_size,
                "created": datetime.fromtimestamp(stat_info.st_ctime),
                "modified": datetime.fromtimestamp(stat_info.st_mtime),
                "accessed": datetime.fromtimestamp(stat_info.st_atime),
                "mime_type": mime_type,
                "extension": Path(file_path).suffix,
                "filename": Path(file_path).name,
                "directory": str(Path(file_path).parent)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi lấy thông tin file: {str(e)}"
            )

    async def delete_file(self, file_path: str, db: Session = None) -> bool:
        """
        Xóa file và bản ghi trong database
        """
        try:
            # Xóa file vật lý
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Xóa bản ghi trong database nếu có
            if db:
                file_record = db.query(FileUpload).filter(
                    FileUpload.file_path == file_path
                ).first()
                
                if file_record:
                    db.delete(file_record)
                    db.commit()
            
            return True
            
        except Exception as e:
            if db:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xóa file: {str(e)}"
            )

    async def clean_temp_files(self, older_than_hours: int = 24) -> int:
        """
        Dọn dẹp file tạm cũ
        """
        try:
            temp_dir = self.upload_dir / "temp"
            if not temp_dir.exists():
                return 0
            
            deleted_count = 0
            cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
            
            for item in temp_dir.iterdir():
                if item.is_file():
                    if item.stat().st_mtime < cutoff_time:
                        item.unlink()
                        deleted_count += 1
                elif item.is_dir():
                    # Xóa thư mục rỗng
                    try:
                        item.rmdir()
                        deleted_count += 1
                    except OSError:
                        # Thư mục không rỗng, bỏ qua
                        pass
            
            return deleted_count
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi dọn dẹp file tạm: {str(e)}"
            )

    async def get_storage_usage(self) -> Dict[str, Any]:
        """
        Lấy thông tin sử dụng dung lượng storage
        """
        try:
            total_size = 0
            file_count = 0
            by_type = {}
            
            for root, dirs, files in os.walk(self.upload_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        
                        # Phân loại theo thư mục
                        relative_path = os.path.relpath(root, self.upload_dir)
                        if relative_path == '.':
                            category = 'root'
                        else:
                            category = relative_path.split(os.sep)[0]
                        
                        if category not in by_type:
                            by_type[category] = {"size": 0, "count": 0}
                        
                        by_type[category]["size"] += file_size
                        by_type[category]["count"] += 1
                        
                    except (OSError, PermissionError):
                        continue
            
            return {
                "total_size": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "by_type": by_type,
                "directory": str(self.upload_dir),
                "last_checked": datetime.now()
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi lấy thông tin storage: {str(e)}"
            )

# Tạo instance singleton
file_service = FileService()