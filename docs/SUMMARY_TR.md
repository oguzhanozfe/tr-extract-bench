# tr-extract-bench — Türkçe özet

`tr-extract-bench`, LLM'lerin Türkçe ticari belgelerden (e-fatura, hesap ekstresi, KAP
özel durum açıklaması, kargo bildirimi) yapılandırılmış JSON çıkarma başarısını ölçen küçük
ve tekrarlanabilir bir benchmark'tır. Tüm belgeler sentetiktir ve kesin doğru cevapları
(ground truth) vardır; VKN, TCKN ve IBAN değerleri kontrol hanesi geçerli ama hayalidir.

Her belge yedi varyantta üretilir: temiz, OCR hatalı, Türkçe karakterleri silinmiş,
TR/EN karışık etiketli, alanları karıştırılmış; ayrıca zor katmanda değerlerin içine de OCR
hatası girmiş (`5→S`, `0→O`) ve dikkat dağıtıcı satırlar eklenmiş varyantlar. Puanlama alan bazındadır: tutarlar
(`1.234,56 TL`), tarihler (`17 Kasım 2026`) ve kimlik numaraları türüne göre normalize
edilir; ayrıca geçerli JSON oranı ve belgede olmayan alanlar için uydurulan değer oranı
(halüsinasyon) raporlanır. [Sonuç tablosu](../README.md) kayıtlı model çıktılarından
yeniden üretilir.

Çalıştırmak için: `python -m unittest discover -s tests` ve `python -m trbench score`.
Kendi modellerinizi denemek için `python -m trbench run`.
