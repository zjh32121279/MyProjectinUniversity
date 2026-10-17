%% 基于离散小波变换与Arnold置乱的数字水印复现
clc; clear; close all;

%% 1. 参数初始化
nw = 64;           % 水印图像分辨率 (64x64) 
arnold_times = 20;  % 正向 Arnold 置乱次数 
arnold_period = 48; % N=64 时的 Arnold 变换周期

%% 2. 读取并预处理图像
% 读取水印图像
watermark = imread('水印图像.bmp');

% 兼容各种水印图片格式
if islogical(watermark)
    % 情况A：如果图片读进来本身就是二值图，直接使用
    watermark = watermark; 
elseif size(watermark, 3) == 3
    % 情况B：标准的 RGB 彩色图像
    watermark = rgb2gray(watermark);
    watermark = imbinarize(watermark);
elseif size(watermark, 3) == 4
    % 情况C：带透明通道的 RGBA 图像
    watermark = rgb2gray(watermark(:,:,1:3));
    watermark = imbinarize(watermark);
else
    % 情况D：普通灰度图像
    watermark = imbinarize(watermark);
end

% 读取载体图像
carrier_name = '载体图像1.bmp'; 
carrier = imread(carrier_name);
if size(carrier, 3) > 1
    carrier = rgb2gray(carrier); % 灰度化处理
end
carrier = double(carrier);

%% ==================== 第一阶段：水印嵌入 ====================
fprintf('--- 开始水印嵌入 ---\n');

% 3. 对水印信息进行 Arnold 置乱
scrambled_w = arnold_transform(watermark, arnold_times);
w_sequence = scrambled_w(:); % 转换为一维 0、1 序列

% 4. 对载体图像进行二级离散小波变换 (使用 Haar 小波)
[ca1, ch1, cv1, cd1] = dwt2(carrier, 'haar');
[ca2, ch2, cv2, cd2] = dwt2(ca1, 'haar'); % 

% 5. 在低频带 ca2 中随机选择 nw*nw 个系数位置 (使用固定种子确保可逆提取)
rng(123); % 固定随机数发生器状态
embed_indices = randperm(numel(ca2), nw * nw); 

% 6. 根据论文公式 (2) 和 (3) 嵌入水印序列
ca2_watermarked = ca2;
for i = 1:(nw * nw)
    pos = embed_indices(i);
    ca = ca2(pos);
    z = mod(ca, nw); % 求余数计算 
    
    if w_sequence(i) == 1
        % 公式 (2)：当 Wa(i) == 1 时
        if z < nw / 4
            ca_prime = ca - nw/4 - z;
        else
            ca_prime = ca + 3*nw/4 - z;
        end
    else
        % 公式 (3)：当 Wa(i) == 0 时
        if z < 3*nw / 4
            ca_prime = ca + nw/4 - z;
        else
            ca_prime = ca + 5*nw/4 - z;
        end
    end
    ca2_watermarked(pos) = ca_prime;
end

% 7. 小波逆变换重构图像
ca1_recon = idwt2(ca2_watermarked, ch2, cv2, cd2, 'haar');
carrier_watermarked = idwt2(ca1_recon, ch1, cv1, cd1, 'haar');
% 限制范围并转回 uint8 格式
carrier_watermarked_uint8 = uint8(max(0, min(255, carrier_watermarked))); 

% 保存含水印图像
imwrite(carrier_watermarked_uint8, '含水印载体图像.bmp');

% 8. 计算嵌入后的峰值信噪比 (PSNR) 
psnr_val = psnr(carrier_watermarked_uint8, uint8(carrier));
fprintf('嵌入后图像的 PSNR 值为: %.4f dB (论文要求 > 30dB)\n', psnr_val);


%% ==================== 第二阶段：水印提取 (盲提取) ====================
fprintf('\n--- 开始盲提取水印 ---\n');

% 9. 对含水印的图像进行二级 Haar 小波分解
[ca1_w, ch1_w, cv1_w, cd1_w] = dwt2(carrier_watermarked, 'haar');
[ca2_w, ch2_w, cv2_w, cd2_w] = dwt2(ca1_w, 'haar'); 

% 10. 根据公式 (4) 提取一维置乱序列
w_extracted_sequence = zeros(nw * nw, 1);
for i = 1:(nw * nw)
    pos = embed_indices(i); % 使用相同的随机位置
    ca_prime = ca2_w(pos);
    z = mod(ca_prime, nw);
    
    % 公式 (4) 提取逻辑
    if z < nw / 2
        w_extracted_sequence(i) = 0;
    else
        w_extracted_sequence(i) = 1;
    end
end

% 11. 重组为二维矩阵，并利用周期性进行逆 Arnold 置乱恢复
w_extracted_scrambled = reshape(w_extracted_sequence, [nw, nw]);
descramble_times = arnold_period - arnold_times; % 48 - 20 = 28 次
watermark_extracted = arnold_transform(w_extracted_scrambled, descramble_times); 
% 12. 计算提取水印与原水印的归一化相关系数 (NC)
W_orig = double(watermark);
W_extr = double(watermark_extracted);
nc_val = sum(sum(W_orig .* W_extr)) / sqrt(sum(sum(W_orig.^2)) * sum(sum(W_extr.^2)));
fprintf('提取出的水印 NC 值为: %.4f (无攻击下理论上应为 1.0000)\n', nc_val); 


%% ==================== 结果可视化 ====================
% --- 1. 准备小波分解的可视化矩阵 ---
% 一级分解布局：展示完整的 1 级 4 个子带 [ca1, ch1; cv1, cd1]
dwt1_visual = [mat2gray(ca1), mat2gray(ch1); ...
               mat2gray(cv1), mat2gray(cd1)];

% 二级分解布局：剥离一级高频，只展示对 ca1 进一步分解后的 4 个二级子带 [ca2, ch2; cv2, cd2]
dwt2_visual = [mat2gray(ca2), mat2gray(ch2); ...
               mat2gray(cv2), mat2gray(cd2)];

figure('Name', '载体图像的小波分解演示', 'NumberTitle', 'off');

% 一级小波分解
subplot(2,1,1); 
imshow(dwt1_visual); 
axis on;  % 开启坐标轴刻度 (0~512)
xlabel('(a) 一级小波分解', 'FontSize', 11, 'FontName', '宋体'); 

% 二级小波分解
subplot(2,1,2); 
imshow(dwt2_visual); 
axis on;  % 开启坐标轴刻度 (此时分辨率减半，刻度自动变为 0~256)
xlabel('(b) 二级小波分解', 'FontSize', 11, 'FontName', '宋体'); 

figure('Name', '数字水印复现结果', 'NumberTitle', 'off');
subplot(2,3,1); imshow(uint8(carrier)); title('1. 原始载体图像');
subplot(2,3,2); imshow(watermark); title('2. 原始水印图像');
subplot(2,3,3); imshow(scrambled_w); title('3. Arnold 置乱水印 (20次)');
subplot(2,3,4); imshow(carrier_watermarked_uint8); title(sprintf('4. 含水印图像\n(PSNR = %.2f dB)', psnr_val));
subplot(2,3,5); imshow(watermark_extracted); title(sprintf('5. 提取的水印\n(NC = %.2f)', nc_val));

%% ==================== 辅助函数：Arnold 置乱算法 ====================
function scrambled = arnold_transform(img, times)
    % img: 输入的二维图像
    % times: 变换迭代次数
    [N, ~] = size(img);
    scrambled = double(img);
    for t = 1:times
        temp = scrambled;
        for x = 1:N
            for y = 1:N
                % 将 MATLAB 的 1 阶坐标转换为 0 阶坐标进行矩阵相乘
                x0 = x - 1;
                y0 = y - 1;
                
                % Arnold 变换矩阵公式：[x'; y'] = [1 1; 1 2] * [x; y] mod N
                nx = mod(x0 + y0, N);     % x' = (x + y) mod N [cite: 30]
                ny = mod(x0 + 2*y0, N);   % y' = (x + 2y) mod N [cite: 30]
                
                % 映射回 MATLAB 的 1 阶坐标
                temp(nx + 1, ny + 1) = scrambled(x, y);
            end
        end
        scrambled = temp;
    end
    scrambled = logical(scrambled); % 保持二值逻辑类型
end