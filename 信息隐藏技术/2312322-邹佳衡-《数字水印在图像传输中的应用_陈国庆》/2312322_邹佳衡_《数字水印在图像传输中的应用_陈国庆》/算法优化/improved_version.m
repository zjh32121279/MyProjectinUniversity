%% 基于离散小波变换与Arnold置乱的数字水印 - 改进版

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
fprintf('\n=== 水印嵌入 ===\n');
tic;

% 3. Arnold置乱
scrambled_w = arnold_transform(watermark, arnold_times);
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

% 6. 按照原论文正确公式嵌入水印
ca2_watermarked = embed_watermark_correct(ca2, w_sequence, nw, embed_indices);

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
fprintf('\n--- 水印提取 ---\n');
tic;

% 8. DWT分解
[ca1_w, ~, ~, ~] = dwt2(double(carrier_watermarked_uint8), 'haar');
[ca2_w, ~, ~, ~] = dwt2(ca1_w, 'haar');

% 9. 提取水印
w_extracted_sequence = extract_watermark_correct(ca2_w, nw, embed_indices);

% 10. 逆Arnold置乱
w_extracted_scrambled = reshape(w_extracted_sequence, [nw, nw]);

period = arnold_period(64);
descramble_times = mod(period - arnold_times, period);
fprintf('Arnold周期: %d, 逆置乱次数: %d\n', period, descramble_times);

watermark_extracted = arnold_transform(w_extracted_scrambled, descramble_times);
watermark_extracted = logical(watermark_extracted);

extract_time = toc;
fprintf('提取完成，耗时: %.4f 秒\n', extract_time);

% 11. 计算NC值
W_orig = double(watermark);
W_extr = double(watermark_extracted);
nc_val = sum(W_orig(:) .* W_extr(:)) / sqrt(sum(W_orig(:).^2) * sum(W_extr(:).^2));
fprintf('NC = %.4f\n', nc_val);

%% ==================== 核心函数 - 正确版本 ====================

function ca2_watermarked = embed_watermark_correct(ca2, w_sequence, nw, embed_indices)
    %% 正确的嵌入公式
    % 核心思想：通过修改系数，使得 mod(ca, nw) 的值落入特定区间
    % 嵌入 1: 将余数调整到 [nw/4, 3nw/4) 区间
    % 嵌入 0: 将余数调整到 [0, nw/4) 或 [3nw/4, nw) 区间
    
    ca2_watermarked = ca2;
    embed_count = length(embed_indices);
    modified_count = 0;
    
    for i = 1:embed_count
        pos = embed_indices(i);
        ca = ca2(pos);
        z = mod(ca, nw);
        
        if w_sequence(i) == 1
            % 嵌入 1: 目标余数范围 [16, 48)  (因为 nw=64, nw/4=16, 3nw/4=48)
            target = 32;  % 目标值取中间值
            delta = target - z;
            % 确保 delta 在合理范围内
            if abs(delta) > nw/4
                if delta > 0
                    delta = delta - nw;
                else
                    delta = delta + nw;
                end
            end
            if delta ~= 0
                modified_count = modified_count + 1;
            end
            ca2_watermarked(pos) = ca + delta;
            
        else
            % 嵌入 0: 目标余数范围 [0, 16) 或 [48, 64)
            % 选择离当前余数最近的目标区间
            if z < 16
                target = 8;  % [0,16) 中间值
            elseif z >= 48
                target = 56; % [48,64) 中间值
            elseif z < 32
                target = 8;  % 靠近 [0,16)
            else
                target = 56; % 靠近 [48,64)
            end
            delta = target - z;
            if abs(delta) > nw/4
                if delta > 0
                    delta = delta - nw;
                else
                    delta = delta + nw;
                end
            end
            if delta ~= 0
                modified_count = modified_count + 1;
            end
            ca2_watermarked(pos) = ca + delta;
        end
    end
    
    fprintf('修改了 %d / %d 个系数 (%.1f%%)\n', modified_count, embed_count, 100*modified_count/embed_count);
end

function extracted_seq = extract_watermark_correct(ca2_w, nw, embed_indices)
    %% 正确的提取公式
    embed_count = length(embed_indices);
    extracted_seq = zeros(embed_count, 1);
    
    for i = 1:embed_count
        pos = embed_indices(i);
        ca = ca2_w(pos);
        z = mod(ca, nw);
        
        % 判断余数落在哪个区间
        if z >= nw/4 && z < 3*nw/4
            extracted_seq(i) = 1;  % 在 [16,48) 区间 -> 嵌入的是 1
        else
            extracted_seq(i) = 0;  % 在 [0,16) 或 [48,64) 区间 -> 嵌入的是 0
        end
    end
end

function scrambled = arnold_transform(img, times)
    %% Arnold置乱
    [N, M] = size(img);
    
    if N ~= M
        error('Arnold变换要求图像为正方形');
    end
    
    scrambled = double(img);
    
    for t = 1:times
        temp = zeros(N, N);
        for x = 1:N
            for y = 1:N
                x0 = x - 1;
                y0 = y - 1;
                nx = mod(x0 + y0, N);
                ny = mod(x0 + 2*y0, N);
                temp(nx + 1, ny + 1) = scrambled(x, y);
            end
        end
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
figure('Name', '数字水印结果', 'NumberTitle', 'off', 'Position', [150, 150, 1200, 500]);

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

% 计算误码率
error_bits = sum(xor(watermark(:), watermark_extracted(:)));
ber = error_bits / numel(watermark);
fprintf('误码率(BER): %.4f%%\n', ber * 100);

if nc_val > 0.99
    fprintf('\n✓ 水印提取成功！\n');
else
    fprintf('\n✗ 仍然有误码，请检查水印图像文件\n');
    fprintf('建议: 使用简单的测试水印重新运行\n');
    
    % 创建简单测试水印
    test_w = false(64, 64);
    test_w(20:44, 20:44) = true;
    imwrite(test_w, 'test_watermark.bmp');
    fprintf('\n已创建测试水印 test_watermark.bmp，请使用这个文件测试\n');
end