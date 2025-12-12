## 導覽列
- [ ] get_by_name : 用name與type(可以是all或是其他單一類別)當參數做模糊查詢，回傳單一或是所有類別(Movie, Company, Director, Actor, Genre, User, Role)中所有相似結果。回傳格式都是該類別Out

## Sign In 頁面
- [ ] get_user_by_email : 用email當參數撈使用者資料，比對完密碼後用回傳基本資料就好。回傳格式UserOut

## User 頁面
- [X] get_review_by_user : 用user_id當參數，撈出所有該使用者的評論過的電影(只統計評論過哪些)。回傳格式MovieOut
- [X] get_genre_by_comment : 用user_id當參數，在所有該使用者的評論過的Movie中，從MovieGenre統計評論數並排序回傳。回傳格式應該要是GenreOut的陣列

## Movie 頁面
- [ ] get_movie_by_id : 用movie_id當參數，先撈電影基本資料再從Owns, RoleInMovie_Played, MovieGenre關聯表撈出該電影所有Genre,Company和出演的Actor。回傳格式包含GenreOut, ActorOut, CompanyOut, MovieOut, DirectorOut
- [ ] get_review_by_id : 用movie_id當參數，從Review找出所有評論回傳，同時計算平均評分。回傳格式ReviewOut跟一個整數
- [ ] create_review : 傳入rating, comment, date並新增到資料庫。傳入格式ReviewIn

## Company 頁面
- [ ] get_company_by_id : 用company_id當參數，撈公司基本資料再從Owns關聯表撈出該公司所有擁有電影。回傳格式CompanyOut, MovieOut

## Actor 頁面
- [ ] get_actor_by_id : 用actor_id當參數，先撈演員基本資料再從RoleInMovie_Played關聯表撈出該演員演出過的所有角色以及出現的電影。回傳格式包含RoleOut, ActorOut, MovieOut

## Advanced Search 頁面
- [ ] get : 傳入advanced_search那頁除了Actor-Director-Combination以外的所有參數組合從資料庫撈出符合的結果，使用者可以決定最後輸出哪個類別的結果(Movie, Company, Director, Actor, Genre, Role擇一，會變成是left join最左邊的表，我不知道結果有沒有差，沒差的話就不用管)。回傳格式都是該結果類別Out(可以用NavOut)
- [ ] get_actor_director_over_k : 傳入參數K，找出合作最頻繁的演員與導演組合，其中要超過K個電影。回傳格式ActorOut, DirectorOut