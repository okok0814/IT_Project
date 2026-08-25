# **BẢN THIẾT KẾ API CONTRACT - HỆ THỐNG TÌM KIẾM THỜI TRANG**

## 1\. Tìm kiếm bằng hình ảnh (Image-to-Image / Upload Search)

Endpoint: POST /api/v1/search/image



Mô tả: Nhận ảnh tải lên từ người dùng, Backend sẽ dùng mô hình CLIP để trích xuất đặc trưng và truy xuất ra 

top các sản phẩm tương đồng nhất thông qua FAISS Index.



Request Body:



image: File (định dạng jpg, png, jpeg)



top\_k: Integer (Số lượng kết quả muốn lấy, mặc định = 10)



Response Trả về (Thành công - 200 OK):

{

"status": "success",

"data": \[

{"product\_id": "42156", "image\_url": "/dataset2/images/42156.jpg", "similarity\_score": 0.94},

{"product\_id": "11234", "image\_url": "/dataset2/images/11234.jpg", "similarity\_score": 0.89}

]

}



## 2\. Tìm kiếm bằng văn bản (Text-to-Image Search)

Endpoint: POST /api/v1/search/text



Mô tả: Nhận chuỗi văn bản mô tả quần áo từ người dùng, dùng CLIP text-encoder mã hóa và tìm kiếm chéo trên FAISS.



Request Body:



query: String (Ví dụ: "áo thun nam màu đen phong cách Y2K")



top\_k: Integer (mặc định = 10)



Response Trả về (Thành công - 200 OK):

{

"status": "success",

"data": \[

{"product\_id": "88211", "image\_url": "/dataset2/images/88211.jpg", "similarity\_score": 0.91},

{"product\_id": "99122", "image\_url": "/dataset2/images/99122.jpg", "similarity\_score": 0.85}

]

}

