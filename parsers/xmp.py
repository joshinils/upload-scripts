from typing import Optional, Tuple, List, Any, Type

from io_storage.storage import Storage
from parsers.base import BaseParser
from common.models import SensorItem, CameraParameters, projection_type_from_name
from xml.etree.ElementTree import fromstring, ParseError


class XMPParser(BaseParser):
    """xmp parser for xmp image header"""

    def __init__(self, file_path: str, storage: Storage):
        super().__init__(file_path, storage)
        self._data_pointer = 0
        self._body_pointer = 0
        self.xmp_str = self._read_xmp()

    def _read_xmp(self) -> str:
        with self._storage.open(self.file_path, "rb") as image:
            d = image.read()
            xmp_start = d.find(b'<x:xmpmeta')
            xmp_end = d.find(b'</x:xmpmeta')
            xmp_str = d[xmp_start:xmp_end + 12]
        return xmp_str

    @classmethod
    def valid_parser(cls, file_path: str, storage: Storage):
        return XMPParser(file_path, storage)

    def next_item_with_class(self, item_class: Type[SensorItem]) -> Optional[SensorItem]:
        if item_class == CameraParameters:
            return self._camera_item()
        return None

    def items_with_class(self, item_class: Type[SensorItem]) -> List[SensorItem]:
        next_item = self.next_item_with_class(item_class)
        if next_item is not None:
            return [next_item]
        return []

    def next_item(self) -> Optional[SensorItem]:
        if self._data_pointer == 0:
            self._data_pointer = 1
        return self._camera_item()

    def items(self) -> List[SensorItem]:
        camera = self._camera_item()
        if camera is not None:
            return [camera]
        return []

    def format_version(self) -> Optional[str]:
        return None

    def serialize(self):
        """this method will write all the added items to file"""
        pass

    def compatible_sensors(self) -> List[Any]:
        return [CameraParameters]

    def _camera_item(self) -> Optional[CameraParameters]:
        try:
            projection = None
            full_pano_image_width = None

            # cropped_area_image_height_pixels = None
            cropped_area_image_width_pixels = None

            root = fromstring(self.xmp_str)
            for element in root.findall("*"):
                for rdf in element.findall("*"):
                    full_pano_image_width, cropped_area_image_width_pixels, projection = self.compute_camera_items(rdf)

                    if cropped_area_image_width_pixels is not None \
                            and full_pano_image_width is not None \
                            and projection is not None:
                        break

                    [full_pano_image_width, cropped_area_image_width_pixels,
                     projection] = self.compute_camera_items_for_garmin(rdf)

            if cropped_area_image_width_pixels is not None \
                    and full_pano_image_width is not None \
                    and projection is not None:
                camera_parameters = CameraParameters()
                camera_parameters.h_fov = cropped_area_image_width_pixels * 360 / full_pano_image_width
                camera_parameters.projection = projection_type_from_name(projection)
                return camera_parameters
            return None
        except ParseError:
            return None

    @staticmethod
    def compute_camera_items(xml_tags) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        full_pano_image_width, cropped_area_image_width_pixels, projection = (None, None, None)
        for attr_name, attr_value in xml_tags.items():
            if "FullPanoWidthPixels" in attr_name:
                full_pano_image_width = int(attr_value)
            if "CroppedAreaImageWidthPixels" in attr_name:
                cropped_area_image_width_pixels = int(attr_value)
            if "ProjectionType" in attr_name:
                projection = attr_value

        return full_pano_image_width, cropped_area_image_width_pixels, projection

    @staticmethod
    def compute_camera_items_for_garmin(xml_elements) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        full_pano_image_width, cropped_area_image_width_pixels, projection = (None, None, None)
        for xml_child in xml_elements.findall("*"):
            if "FullPanoWidthPixels" in xml_child.tag:
                full_pano_image_width = int(xml_child.text)
            if "CroppedAreaImageWidthPixels" in xml_child.tag:
                cropped_area_image_width_pixels = int(xml_child.text)
            if "ProjectionType" in xml_child.tag:
                projection = xml_child.text

        return full_pano_image_width, cropped_area_image_width_pixels, projection
