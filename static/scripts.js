// script.js

document.addEventListener('DOMContentLoaded', () => {
    // URL của API backend (sử dụng đường dẫn tương đối)
    const API_ENDPOINT = '/api/analyze';

    // Lấy các phần tử DOM
    const textInput = document.getElementById('text-input');
    const charCounter = document.getElementById('char-counter');
    const pasteBtn = document.getElementById('paste-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const clearBtn = document.getElementById('clear-btn');
    const resultCardContainer = document.getElementById('result-card-container');
    const resultCard = document.getElementById('result-card');

    const MAX_CHARS = 10000; // Đồng bộ với maxlength của textarea
    const analyzeBtnOriginalHTML = analyzeBtn.innerHTML;

    // --- CÁC HÀM TIỆN ÍCH ---

    function setControlsDisabled(disabled) {
        textInput.disabled = disabled;
        analyzeBtn.disabled = disabled;
        pasteBtn.disabled = disabled;
        clearBtn.disabled = disabled;
    }

    // --- CÁC HÀM XỬ LÝ SỰ KIỆN ---

    // Dán từ Clipboard
    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            textInput.value = text;
            updateCharCounter();
            textInput.focus();
        } catch (err) {
            console.error('Không thể dán văn bản: ', err);
            displayError("Trình duyệt của bạn không hỗ trợ hoặc đã từ chối quyền truy cập clipboard.");
        }
    });

    // Xóa toàn bộ
    clearBtn.addEventListener('click', () => {
        textInput.value = '';
        updateCharCounter();
        resultCard.innerHTML = '';
        resultCardContainer.className = ''; // Xóa class để CSS ẩn đi
        textInput.focus();
    });

    // Bắt đầu quá trình phân tích
    analyzeBtn.addEventListener('click', () => {
        const textToAnalyze = textInput.value;
        if (textToAnalyze.trim() === '') {
            displayError("Dữ liệu đầu vào rỗng. Vui lòng nhập văn bản để phân tích.");
            return;
        }
        if (textToAnalyze.length > MAX_CHARS) {
            displayError(`Nội dung quá dài. Giới hạn là ${MAX_CHARS} ký tự.`);
            return;
        }
        performAnalysis(textToAnalyze);
    });

    // Cập nhật bộ đếm ký tự
    textInput.addEventListener('input', updateCharCounter);

    // --- CÁC HÀM CHÍNH ---

    async function performAnalysis(text) {
        setControlsDisabled(true);
        analyzeBtn.innerHTML = '<div class="loader-small"></div> Đang phân tích...';
        resultCardContainer.className = 'loading'; // Thêm class để CSS hiển thị
        resultCard.innerHTML = '<div class="loader"></div><p style="text-align:center; margin-top:1rem;">Đang kết nối tới Anna-AI...</p>';

        try {
            // 2. Gọi API bằng fetch
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: text })
            });

            // 3. Xử lý phản hồi
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Lỗi máy chủ: ${response.status}`);
            }

            const data = await response.json();
            
            // 4. Hiển thị kết quả thành công
            displayResults(data.result);

        } catch (error) {
            // 5. Xử lý lỗi (mạng, máy chủ, etc.)
            console.error('Lỗi khi phân tích:', error);
            displayError(error.message);
        } finally {
            setControlsDisabled(false);
            analyzeBtn.innerHTML = analyzeBtnOriginalHTML;
        }
    }

    function displayResults(result) {
        resultCardContainer.className = result.is_dangerous ? 'dangerous' : 'safe';
        
        const statusText = result.is_dangerous ? "CẢNH BÁO NGUY HIỂM" : "TÍN HIỆU AN TOÀN";
        
        const resultHTML = `
            <h2 id="result-status">${statusText}</h2>
            <div class="result-details">
                <ul>
                    <li><span class="label">//:Lý do:</span> ${result.reason || 'Không có'}</li>
                    <li><span class="label">//:Khuyến cáo:</span> ${result.recommend || 'Không có'}</li>
                    <li><span class="label">//:Phân loại:</span> ${result.types || 'Không xác định'}</li>
                    <li><span class="label">//:Mức độ rủi ro:</span> ${result.score || 0} / 5</li>
                </ul>
            </div>
        `;
        resultCard.innerHTML = resultHTML;
    }

    function displayError(errorMessage) {
        resultCardContainer.className = 'error';
        resultCard.innerHTML = `
            <h2 id="result-status">LỖI KẾT NỐI</h2>
            <div class="result-details">
                <p>${errorMessage}</p>
            </div>
        `;
    }

    function updateCharCounter() {
        const count = textInput.value.length;
        charCounter.textContent = `${count} / ${MAX_CHARS}`;
        charCounter.style.color = count > MAX_CHARS ? 'var(--danger-color)' : 'inherit';
    }

    // Khởi tạo
    updateCharCounter();
});