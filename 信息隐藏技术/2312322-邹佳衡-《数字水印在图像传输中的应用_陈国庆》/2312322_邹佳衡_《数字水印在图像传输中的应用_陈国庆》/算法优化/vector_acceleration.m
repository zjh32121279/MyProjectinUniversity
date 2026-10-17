A%% 基于离散小波变换与Arnold置乱的数字水印 - 向量化加速版
%% 相比原论文改进：1)修正嵌入公式 2)100%系数利用 3)向量化加速

clc; clear; close all;

%% ==================== 1. 参数初始化 ====================
nw = 64;                % 水印图像分辨率 (64x64) 
arnold_times = 20;      % 正向 Arnold 置乱次数 

%% ==================== 2. 读取并预处理图像 ====================
% 读取水印图像
watermark = imread('水印图像.bmp');

% 确保水印是二值图像
if islogical(watermark)
    watermark = watermark; 
elseif size(watermark, 3) == 3
    watermark = rgb2gray(watermark);
    watermark = imbinarize(watermark);
else
    watermark = imbinarize(watermark);
end

% 确保水印尺寸是64x64
if size(watermark, 1) ~= 64 || size(watermark, 2) ~= 64
    watermark = imresize(watermark, [64, 64]);
    watermark = watermark > 0.5;
end

fprintf('水印尺寸: %dx%d\n', size(watermark,1), size(watermark,2));
fprintf('水印中1的比例: %.2f%%\n', 100*sum(watermark(:))/numel(watermark));

% 读取载体图像
carrier_name = '载体图像1.bmp'; 
carrier = imread(carrier_name);
if size(carrier, 3) > 1
    carrier = rgb2gray(carrier);
end
carrier = double(carrier);

%% ==================== 第一阶段：水印嵌入 ====================
fprintf('\n=== 水印嵌入 (向量化加速版) ===\n');
tic;

% 3. Arnold置乱
scrambled_w = arnold_transform_vectorized(watermark, arnold_times);
w_sequence = scrambled_w(:);
embed_count = nw * nw;

% 4. 二级DWT分解
[ca1, ch1, cv1, cd1] = dwt2(carrier, 'haar');
[ca2, ch2, cv2, cd2] = dwt2(ca1, 'haar');

fprintf('ca2尺寸: %dx%d, 系数总数: %d\n', size(ca2,1), size(ca2,2), numel(ca2));

% 5. 选择嵌入位置
rng(123);
total_coeffs = numel(ca2);
embed_indices = randperm(total_coeffs, embed_count);

% 6. 向量化嵌入水印 (核心加速)
ca2_watermarked = vectorized_embed(ca2, w_sequence, nw, embed_indices);

% 7. 小波逆变换
ca1_recon = idwt2(ca2_watermarked, ch2, cv2, cd2, 'haar');
carrier_watermarked = idwt2(ca1_recon, ch1, cv1, cd1, 'haar');

carrier_watermarked_uint8 = uint8(max(0, min(255, carrier_watermarked)));

embed_time = toc;
fprintf('嵌入完成，耗时: %.4f 秒\n', embed_time);

% 计算PSNR
psnr_val = psnr(carrier_watermarked_uint8, uint8(carrier));
fprintf('PSNR = %.4f dB\n', psnr_val);

%% ==================== 第二阶段：水印提取 ====================
fprintf('\n--- 水印提取 (向量化加速版) ---\n');
tic;

% 8. DWT分解
[ca1_w, ~, ~, ~] = dwt2(double(carrier_watermarked_uint8), 'haar');
[ca2_w, ~, ~, ~] = dwt2(ca1_w, 'haar');

% 9. 向量化提取水印
w_extracted_sequence = vectorized_extract(ca2_w, nw, embed_indices);

% 10. 逆Arnold置乱
w_extracted_scrambled = reshape(w_extracted_sequence, [nw, nw]);

period = arnold_period(64);
descramble_times = mod(period - arnold_times, period);
fprintf('Arnold周期: %d, 逆置乱次数: %d\n', period, descramble_times);

watermark_extracted = arnold_transform_vectorized(w_extracted_scrambled, descramble_times);
watermark_extracted = logical(watermark_extracted);

extract_time = toc;
fprintf('提取完成，耗时: %.4f 秒\n', extract_time);

% 11. 计算NC值
W_orig = double(watermark);
W_extr = double(watermark_extracted);
nc_val = sum(W_orig(:) .* W_extr(:)) / sqrt(sum(W_orig(:).^2) * sum(W_extr(:).^2));
fprintf('NC = %.4f\n', nc_val);

if nc_val > 0.99
    fprintf('✓ 水印提取成功！\n');
else
    fprintf('✗ 水印提取不完整\n');
end

fprintf('\n=== 性能对比 ===\n');
fprintf('循环版本: 嵌入~0.055s, 提取~0.027s\n');
fprintf('向量化版本: 嵌入%.4fs, 提取%.4fs\n', embed_time, extract_time);
fprintf('加速比: %.1fx\n', (0.055+0.027)/(embed_time+extract_time));

%% ==================== 向量化核心函数 ====================

function ca2_watermarked = vectorized_embed(ca2, w_sequence, nw, embed_indices)
    %% 完全向量化的水印嵌入 (无循环)
    % 相比原论文改进: 100%系数修改，目标值量化
    
    % 提取所有需要嵌入的系数
    ca_values = ca2(embed_indices);
    z_values = mod(ca_values, nw);
    
    % 预分配目标余数
    target_z = zeros(size(ca_values));
    
    % 向量化确定目标余数
    % 嵌入1: 目标余数 = 32 (nw/2)
    % 嵌入0: 目标余数 = 8 或 56 (离当前最近的端点)
    mask1 = (w_sequence == 1);
    target_z(mask1) = nw/2;  % 32
    
    mask0 = (w_sequence == 0);
    % 对于嵌入0，选择最近的端点 (8 或 56)
    z0 = z_values(mask0);
    target_z0 = zeros(size(z0));
    target_z0(z0 < nw/2) = nw/8;      % 8
    target_z0(z0 >= nw/2) = 7*nw/8;   % 56
    target_z(mask0) = target_z0;
    
    % 计算需要的增量
    delta = target_z - z_values;
    
    % 将delta调整到 [-nw/4, nw/4] 范围 (最小化修改)
    delta(delta > nw/4) = delta(delta > nw/4) - nw;
    delta(delta < -nw/4) = delta(delta < -nw/4) + nw;
    
    % 一次性更新所有系数
    ca2_watermarked = ca2;
    ca2_watermarked(embed_indices) = ca_values + delta;
end

function extracted_seq = vectorized_extract(ca2_w, nw, embed_indices)
    %% 完全向量化的水印提取 (无循环)
    
    % 提取所有系数并计算余数
    ca_values = ca2_w(embed_indices);
    z_values = mod(ca_values, nw);
    
    % 向量化判断: 余数在 [nw/4, 3nw/4) 区间 -> 1, 否则 -> 0
    extracted_seq = zeros(length(z_values), 1);
    extracted_seq(z_values >= nw/4 & z_values < 3*nw/4) = 1;
end

function scrambled = arnold_transform_vectorized(img, times)
    %% 向量化Arnold置乱 (优化版)
    [N, M] = size(img);
    
    if N ~= M
        error('Arnold变换要求图像为正方形');
    end
    
    % 对于小尺寸图像，循环已经足够快，但使用预计算优化
    scrambled = double(img);
    
    for t = 1:times
        % 预计算所有新坐标
        [X, Y] = meshgrid(0:N-1, 0:N-1);
        newX = mod(X + Y, N);
        newY = mod(X + 2*Y, N);
        
        % 转换为线性索引
        old_idx = sub2ind([N, N], X(:)+1, Y(:)+1);
        new_idx = sub2ind([N, N], newX(:)+1, newY(:)+1);
        
        % 一次性重映射所有像素
        temp = scrambled;
        temp(new_idx) = scrambled(old_idx);
        scrambled = temp;
    end
    
    scrambled = logical(scrambled);
end

function period = arnold_period(N)
    %% 计算Arnold变换周期
    period_table = [2,3; 3,4; 4,3; 5,10; 6,12; 7,8; 8,6; 9,12; 10,30; 
                    16,24; 32,24; 50,150; 64,48; 100,150; 128,96; 256,192; 512,384];
    
    for i = 1:size(period_table, 1)
        if period_table(i, 1) == N
            period = period_table(i, 2);
            return;
        end
    end
    
    period = 1;
    temp = [1; 0];
    A = [1 1; 1 2];
    while true
        temp = mod(A * temp, N);
        period = period + 1;
        if isequal(temp, [1; 0])
            break;
        end
    end
end

%% ==================== 结果可视化 ====================

% 小波分解可视化
figure('Name', '载体图像的小波分解演示', 'NumberTitle', 'off', 'Position', [100, 100, 800, 600]);

% 一级分解
[ca1, ch1, cv1, cd1] = dwt2(carrier, 'haar');
[h1, w1] = size(ca1);
ch1_resized = imresize(ch1, [h1, w1]);
cv1_resized = imresize(cv1, [h1, w1]);
cd1_resized = imresize(cd1, [h1, w1]);

dwt1_visual = [mat2gray(ca1), mat2gray(ch1_resized); 
               mat2gray(cv1_resized), mat2gray(cd1_resized)];

subplot(2,1,1);
imshow(dwt1_visual);
axis on;
title('(a) 一级小波分解', 'FontSize', 11);

% 二级分解
[ca2, ch2, cv2, cd2] = dwt2(ca1, 'haar');
[h2, w2] = size(ca2);
ch2_resized = imresize(ch2, [h2, w2]);
cv2_resized = imresize(cv2, [h2, w2]);
cd2_resized = imresize(cd2, [h2, w2]);

dwt2_visual = [mat2gray(ca2), mat2gray(ch2_resized); 
               mat2gray(cv2_resized), mat2gray(cd2_resized)];

subplot(2,1,2);
imshow(dwt2_visual);
axis on;
title('(b) 二级小波分解', 'FontSize', 11);

% 水印结果可视化
figure('Name', '数字水印结果 - 向量化加速版', 'NumberTitle', 'off', 'Position', [150, 150, 1200, 500]);

subplot(2,3,1);
imshow(uint8(carrier));
title('1. 原始载体图像');

subplot(2,3,2);
imshow(watermark);
title(sprintf('2. 原始水印\n(1占%.1f%%)', 100*sum(watermark(:))/numel(watermark)));

subplot(2,3,3);
imshow(scrambled_w);
title(sprintf('3. Arnold置乱 (%d次)', arnold_times));

subplot(2,3,4);
imshow(carrier_watermarked_uint8);
title(sprintf('4. 含水印图像\nPSNR = %.2f dB', psnr_val));

subplot(2,3,5);
imshow(watermark_extracted);
title(sprintf('5. 提取水印\nNC = %.4f', nc_val));

subplot(2,3,6);
diff_img = abs(double(carrier) - double(carrier_watermarked_uint8));
imshow(diff_img * 10, []);
title('6. 差异图像 (×10放大)');
colormap(gca, 'hot');
colorbar;

% 详细验证
fprintf('\n=== 验证信息 ===\n');
fprintf('原始水印 - 1的数量: %d, 0的数量: %d\n', sum(watermark(:)), sum(~watermark(:)));
fprintf('提取水印 - 1的数量: %d, 0的数量: %d\n', sum(watermark_extracted(:)), sum(~watermark_extracted(:)));

error_bits = sum(xor(watermark(:), watermark_extracted(:)));
ber = error_bits / numel(watermark);
fprintf('误码率(BER): %.4f%%\n', ber * 100);