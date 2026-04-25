from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = PROJECT_ROOT / "ocr_models"
REQUIRED_CNOCR_MODEL = (
    "2.3",
    "densenet_lite_136-gru",
    "cnocr-v2.3-densenet_lite_136-gru-epoch=004-ft-model.onnx",
)


def copy_tree(source: Path, target: Path) -> int:
    copied = 0
    for src in source.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(source)
        dst = target / rel
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def ensure_cnocr_cache():
    from cnocr import CnOcr
    from cnocr.utils import data_dir as cnocr_data_dir

    cnocr_root = Path(cnocr_data_dir())
    required_fp = cnocr_root.joinpath(*REQUIRED_CNOCR_MODEL)
    if required_fp.exists():
        return cnocr_root

    print("[OCR] 本机缺少 CnOCR 识别模型，开始初始化下载/生成缓存...")
    CnOcr(det_model_name="naive_det")
    if not required_fp.exists():
        raise RuntimeError(f"CnOCR 模型缓存生成失败: {required_fp}")
    return cnocr_root


def main():
    cnocr_root = ensure_cnocr_cache()
    source = cnocr_root.joinpath(*REQUIRED_CNOCR_MODEL[:-1])
    target = BUNDLE_ROOT / "cnocr" / Path(*REQUIRED_CNOCR_MODEL[:-1])
    copied = copy_tree(source, target)

    try:
        from cnstd.utils import data_dir as cnstd_data_dir

        cnstd_root = Path(cnstd_data_dir())
        if cnstd_root.exists():
            copied += copy_tree(cnstd_root, BUNDLE_ROOT / "cnstd")
    except Exception as exc:
        print(f"[OCR] 跳过 CnSTD 模型缓存复制: {exc}")

    bundled_required = BUNDLE_ROOT / "cnocr" / Path(*REQUIRED_CNOCR_MODEL)
    if not bundled_required.exists():
        raise RuntimeError(f"发布包 OCR 模型准备失败: {bundled_required}")

    print(f"[OCR] OCR 模型资源已准备: {BUNDLE_ROOT}，新增/更新 {copied} 个文件。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[OCR] 准备 OCR 模型失败: {exc}", file=sys.stderr)
        sys.exit(1)
