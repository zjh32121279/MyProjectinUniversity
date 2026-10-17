% 两张含水印载体图像的攻击测试与 NC 分析
% 运行前请更新下方路径

clear; clc;

% === 输入 ===
baseDir = fileparts(mfilename('fullpath'));
imgPath1 = fullfile(baseDir, 'instance', 'carrier1.bmp');
imgPath2 = fullfile(baseDir, 'instance', 'carrier2.bmp');

% 若有原始水印图像，用于 NC 计算
% 若没有，则与“未攻击时提取的水印”作为参考
wmRefPath = fullfile(baseDir, 'instance', 'watermark.bmp');

% 输出文件夹
outDir = fullfile(baseDir, 'result');
if ~exist(outDir, 'dir')
    mkdir(outDir);
end

% === 读取图像 ===
I1 = double(imread(imgPath1));
I2 = double(imread(imgPath2));

% 读取参考水印（如果有）
hasWmRef = exist(wmRefPath, 'file') == 2;
if hasWmRef
    Wref = double(binarize_watermark(imread(wmRefPath)));
else
    Wref = [];
end

% 定义攻击
attacks = {
    struct('name','gaussian_filter','fn',@(I) imgaussfilt(I, 1.0))
    struct('name','median_filter','fn',@(I) medfilt2_gray_or_rgb(I, [3 3]))
    struct('name','salt_pepper','fn',@(I) (imnoise(mat2gray(I), 'salt & pepper', 0.02) * 255))
    struct('name','jpeg','fn',@(I) jpeg_attack(mat2gray(I), 50, outDir))
    struct('name','rotate','fn',@(I) rotate_attack(I, 5))
    struct('name','scale','fn',@(I) scale_attack(I, 1.2))
    struct('name','crop','fn',@(I) crop_attack(I, 0.8))
};

% 两张图像分别处理
% 水印提取参数（需与嵌入时一致）
nw = 64;
arnold_times = 20;
arnold_period = 48;

run_attack_suite('img1', I1, Wref, hasWmRef, attacks, outDir, nw, arnold_times, arnold_period);
run_attack_suite('img2', I2, Wref, hasWmRef, attacks, outDir, nw, arnold_times, arnold_period);

% === 本地函数 ===
function run_attack_suite(tag, I, Wref, hasWmRef, attacks, outDir, nw, arnold_times, arnold_period)
    fprintf('Processing %s...\n', tag);
    atkCount = numel(attacks);
    atkImages = cell(atkCount, 1);
    wmImages = cell(atkCount, 1);
    ncValues = zeros(atkCount, 1);
    for k = 1:numel(attacks)
        atk = attacks{k};
        Iatk = atk.fn(I);
        outPath = fullfile(outDir, sprintf('%s_%s.png', tag, atk.name));
        imwrite(to_uint8_display(Iatk), outPath);

        Wext = extract_watermark_from_image(Iatk, nw, arnold_times, arnold_period);

        if hasWmRef
            nc = nc_coeff(Wref, Wext);
            fprintf('%s %s NC=%.4f\n', tag, atk.name, nc);
        else
            % 无参考水印时，用未攻击图像的提取结果作参考
            Wref_local = extract_watermark_from_image(I, nw, arnold_times, arnold_period);
            nc = nc_coeff(Wref_local, Wext);
            fprintf('%s %s NC=%.4f (ref from clean WM)\n', tag, atk.name, nc);
        end

        atkImages{k} = Iatk;
        wmImages{k} = Wext;
        ncValues(k) = nc;
    end

    % 展示各攻击后图像与对应提取水印
    figure('Name', sprintf('%s 攻击结果与水印', tag), 'NumberTitle', 'off');
    for k = 1:atkCount
        subplot(2, atkCount, k);
        imshow(to_uint8_display(atkImages{k}));
        title(attacks{k}.name, 'Interpreter', 'none');

        subplot(2, atkCount, atkCount + k);
        imshow(to_uint8_display(wmImages{k}));
        title(sprintf('NC=%.3f', ncValues(k)));
    end
end

function W = extract_watermark_from_image(I, nw, arnold_times, arnold_period)
    % 从含水印载体图像中盲提取水印
    if size(I, 3) > 1
        I = rgb2gray(I);
    end
    I = double(I);

    % 二级 Haar 小波分解
    [ca1_w, ~, ~, ~] = dwt2(I, 'haar');
    [ca2_w, ~, ~, ~] = dwt2(ca1_w, 'haar');

    % 与嵌入一致的随机位置
    rng(123);
    embed_indices = randperm(numel(ca2_w), nw * nw);

    % 提取一维置乱序列
    w_extracted_sequence = zeros(nw * nw, 1);
    for i = 1:(nw * nw)
        pos = embed_indices(i);
        ca_prime = ca2_w(pos);
        z = mod(ca_prime, nw);
        if z < nw / 2
            w_extracted_sequence(i) = 0;
        else
            w_extracted_sequence(i) = 1;
        end
    end

    % 逆 Arnold 置乱
    w_extracted_scrambled = reshape(w_extracted_sequence, [nw, nw]);
    descramble_times = arnold_period - arnold_times;
    W = arnold_transform(w_extracted_scrambled, descramble_times);
end

function out = medfilt2_gray_or_rgb(I, win)
    if ndims(I) == 2
        out = medfilt2(I, win);
    else
        out = I;
        for c = 1:size(I, 3)
            out(:,:,c) = medfilt2(I(:,:,c), win);
        end
    end
end

function Iout = jpeg_attack(I, quality, outDir)
    tmp = fullfile(outDir, 'tmp_jpeg_attack.jpg');
    imwrite(I, tmp, 'Quality', quality);
    Iout = double(imread(tmp));
end

function Iout = rotate_attack(I, angleDeg)
    Iout = imrotate(I, angleDeg, 'bilinear', 'crop');
end

function Iout = scale_attack(I, scaleFactor)
    Iout = imresize(I, scaleFactor, 'bicubic');
    % 还原尺寸，便于公平比较
    Iout = imresize(Iout, [size(I,1) size(I,2)], 'bicubic');
end

function Iout = crop_attack(I, keepRatio)
    h = size(I, 1);
    w = size(I, 2);
    ch = max(1, round(h * keepRatio));
    cw = max(1, round(w * keepRatio));
    y1 = floor((h - ch) / 2) + 1;
    x1 = floor((w - cw) / 2) + 1;
    Icrop = I(y1:y1+ch-1, x1:x1+cw-1, :);
    Iout = imresize(Icrop, [h w], 'bicubic');
end

function nc = nc_coeff(A, B)
    A = A(:);
    B = B(:);
    if numel(A) ~= numel(B)
        minLen = min(numel(A), numel(B));
        A = A(1:minLen);
        B = B(1:minLen);
    end
    denom = sqrt(sum(A.^2) * sum(B.^2));
    if denom == 0
        nc = 0;
    else
        nc = sum(A .* B) / denom;
    end
end

function scrambled = arnold_transform(img, times)
    [N, ~] = size(img);
    scrambled = double(img);
    for t = 1:times
        temp = scrambled;
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

function W = binarize_watermark(watermark)
    % 统一将参考水印处理为二值图，避免类型不匹配
    if islogical(watermark)
        W = watermark;
    elseif size(watermark, 3) == 3
        W = imbinarize(rgb2gray(watermark));
    elseif size(watermark, 3) == 4
        W = imbinarize(rgb2gray(watermark(:,:,1:3)));
    else
        W = imbinarize(watermark);
    end
end

function Iout = to_uint8_display(I)
    if isa(I, 'uint8')
        Iout = I;
        return;
    end
    Imin = min(I(:));
    Imax = max(I(:));
    if Imax <= 1 && Imin >= 0
        Iout = im2uint8(I);
    else
        Iout = uint8(max(0, min(255, I)));
    end
end
