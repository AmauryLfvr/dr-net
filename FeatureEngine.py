from typing import List
from Token import Token
from Invoice import InvoicePage
import math
import json
import os
from Invoice import Invoice, InvoicePage


class FeatureEngine:
    @classmethod
    def map_labels_to_invoice_OCR(self, data_path: str, verbose: bool = False):
        # This tuple represents the number of pages to do OCR for for each invoice. Eg. (2,1) represents do OCR for the first 2 pages, and for the last page
        RANGE_OF_PAGES_FOR_OCR = (2, 2)
        invoices = []
        for filename in os.listdir(data_path):
            if filename.endswith(".pdf"):

                # First check if json tags are present. If they aren't, skip this pdf
                if not os.path.exists(data_path + "/" + filename[:-4] + ".json"):
                    print(
                        "Warning: json tags for",
                        filename,
                        "does not exist. Check if they are in the same folder. Skipping this pdf",
                    )
                    continue

                # Next, do OCR for the relevant pages in the invoice
                invoice = Invoice(data_path + "/" + filename)
                if verbose:
                    print("Processing:", invoice.readable_name)

                if invoice.length() < sum(RANGE_OF_PAGES_FOR_OCR):
                    for page in invoice.pages:
                        page.do_OCR(verbose=verbose)
                else:
                    for page in invoice.pages[: RANGE_OF_PAGES_FOR_OCR[0]]:
                        page.do_OCR(verbose=verbose)
                    for page in invoice.pages[-RANGE_OF_PAGES_FOR_OCR[1] :]:
                        page.do_OCR(verbose=verbose)

                # Try mapping labels
                invoice.map_labels(verbose=verbose)
                invoices.append(invoice)
                invoice.save_data()

        return invoices

    @classmethod
    def create_features(self, token: Token, invoicePage: InvoicePage):

        ################################### HELPER FUNCTIONS FOR TOKEN GENERATION #################################################
        # calculates and returns min dist from token 1 to token 2 in pixels
        def calc_min_dist(t1, t2):
            # get bounding outer rectangle
            outer_rect_left = min(t1.coordinates["x"], t2.coordinates["x"])
            outer_rect_top = min(t1.coordinates["y"], t2.coordinates["y"])
            outer_rect_bottom = max(
                (t1.coordinates["y"] + t1.coordinates["height"]),
                (t2.coordinates["y"] + t2.coordinates["height"]),
            )
            outer_rect_right = max(
                (t1.coordinates["x"] + t1.coordinates["width"]),
                (t2.coordinates["x"] + t2.coordinates["width"]),
            )
            outer_rect_width = outer_rect_right - outer_rect_left
            outer_rect_heigth = outer_rect_bottom - outer_rect_top
            inner_rect_width = max(
                0,
                outer_rect_width - (t1.coordinates["width"] + t2.coordinates["width"]),
            )
            inner_rect_height = max(
                0,
                outer_rect_heigth
                - (t1.coordinates["height"] + t2.coordinates["height"]),
            )
            pixel_dist = math.sqrt(inner_rect_width ** 2 + inner_rect_height ** 2)
            return pixel_dist

        # checks if two tokens are aligned vertically within a margin of error (checks midpoint, left boundary, right boundary)
        def is_vert_aligned(t1, t2, moe):
            if abs(t1.coordinates["x"] - t2.coordinates["x"]) < moe:
                return True
            if (
                abs(
                    (t1.coordinates["x"] + t1.coordinates["width"])
                    - (t2.coordinates["x"] + t2.coordinates["width"])
                )
                < moe
            ):
                return True
            t1_midpt_x = t1.coordinates["x"] + (t1.coordinates["width"] / 2)
            t2_midpt_x = t2.coordinates["x"] + (t2.coordinates["width"] / 2)
            if abs(t1_midpt_x - t2_midpt_x) < moe:
                return True
            return False

        # checks if two tokens are aligned horizontally within a margin of error (checks midpoint, top boundary, bottom boundary)
        def is_hori_aligned(t1, t2, moe):
            if abs(t1.coordinates["y"] - t2.coordinates["y"]) < moe:
                return True
            if (
                abs(
                    (t1.coordinates["y"] + t1.coordinates["height"])
                    - (t2.coordinates["y"] + t2.coordinates["height"])
                )
                < moe
            ):
                return True
            t1_midpt_y = t1.coordinates["y"] + (t1.coordinates["height"] / 2)
            t2_midpt_y = t2.coordinates["y"] + (t2.coordinates["height"] / 2)
            if abs(t1_midpt_y - t2_midpt_y) < moe:
                return True
            return False

        #############################################################################################################################

        features = {}

        # number of characters and words in token text string
        features["char_count"] = len(token.text)
        features["word_count"] = len(token.text.split(" "))

        # height and width of token
        features["height"] = token.coordinates["height"]
        features["width"] = token.coordinates["width"]

        # distance to edges of page (to nearest point on the box)
        features["dist_top"] = token.coordinates["y"]
        features["dist_left"] = token.coordinates["x"]
        features["dist_bottom"] = invoicePage.size["y"] - (
            token.coordinates["y"] + token.coordinates["height"]
        )
        features["dist_right"] = invoicePage.size["x"] - (
            token.coordinates["x"] + token.coordinates["width"]
        )

        # distance to boundaries of outermost text on page (tokens nearest to edge of page)
        min_x = 99999#math.inf
        min_y = 99999#math.inf
        max_y = 0
        max_x = 0
        for t in invoicePage.grouped_tokens:
            if t.coordinates["x"] < min_x:
                min_x = t.coordinates["x"]
            if t.coordinates["y"] < min_y:
                min_y = t.coordinates["y"]
            if t.coordinates["x"] + t.coordinates["width"] > max_x:
                max_x = t.coordinates["x"] + t.coordinates["width"]
            if t.coordinates["y"] + t.coordinates["height"] > max_y:
                max_y = t.coordinates["y"] + t.coordinates["height"]
        features["dist_top_outer"] = token.coordinates["y"] - min_x
        features["dist_left_outer"] = token.coordinates["x"] - min_y
        features["dist_bottom_outer"] = max_y - (
            token.coordinates["y"] + token.coordinates["height"]
        )
        features["dist_right_outer"] = max_x - (
            token.coordinates["x"] + token.coordinates["width"]
        )

        # relative size of token box compared to page
        features["rel_size_page_x"] = token.coordinates["width"] / invoicePage.size["x"]
        features["rel_size_page_y"] = (
            token.coordinates["height"] / invoicePage.size["y"]
        )

        # ave dist to neighbours (pixel and relative)
        min_dist_neighbours = [
            calc_min_dist(t, token) for t in invoicePage.grouped_tokens
        ]
        features["average_dist_neighbours_pixel"] = sum(min_dist_neighbours) / len(
            min_dist_neighbours
        )
        invoice_diag = math.sqrt(
            invoicePage.size["y"] ** 2 + invoicePage.size["x"] ** 2
        )
        features["average_dist_neighbours_rel"] = (
            features["average_dist_neighbours_pixel"] / invoice_diag
        )
        N = 5  # N is arbitrary
        min_dist_neighbours.sort()
        N_nearest_neighbours = min_dist_neighbours[:N]
        features["average_dist_N_nearest_neighbours_pixel"] = sum(
            N_nearest_neighbours
        ) / len(N_nearest_neighbours)
        features["average_dist_N_nearest_neighbours_rel"] = (
            features["average_dist_N_nearest_neighbours_pixel"] / invoice_diag
        )

        # relative size compared to other tokens (percentile)
        perc_w = 0
        perc_h = 0
        for t in invoicePage.grouped_tokens:
            if t is not token:
                if t.coordinates["width"] < token.coordinates["width"]:
                    perc_w += 1
                if t.coordinates["height"] < token.coordinates["height"]:
                    perc_h += 1
        features["percentile_width"] = perc_w / len(invoicePage.grouped_tokens)
        features["percentile_height"] = perc_h / len(invoicePage.grouped_tokens)

        # boolean if token contains fields
        features["contains_date"] = 1 if token.date_values else 0
        features["contains_currency"] = 1 if token.currency else 0
        features["contains_address"] = 1 if token.address else 0
        features["contains_num_label"] = 1 if token.num_label else 0
        features["contains_total_label"] = 1 if token.total_label else 0
        features["contains_date_label"] = 1 if token.date_label else 0
        features["contains_date_of_invoice_label"] = 1 if features["contains_date_label"] and len(token.date_label.split(" ")) > 1 else 0 # This is a more specific feature that the one above
        features["contains_digit"] = 1 if token.contains_digit else 0
        features["contains_company"] = 1 if token.company else 0

        # boolean if aligned with selected tokens
        moe = 10  # arbitary 10 pixle margin of error
        features["vert_align_to_cell_w_date"] = 0
        features["vert_align_to_cell_w_currency"] = 0
        features["vert_align_to_cell_w_address"] = 0
        features["vert_align_to_cell_w_datelabel"] = 0
        features["vert_align_to_cell_w_dateofinvoicelabel"] = 0
        features["vert_align_to_cell_w_numlabel"] = 0
        features["vert_align_to_cell_w_totallabel"] = 0
        features["vert_align_to_cell_w_digit"] = 0
        features["vert_align_to_cell_w_invoicenum_label"] = 0
        features["vert_align_to_cell_w_accountnum_label"] = 0
        features["vert_align_to_cell_w_ponum_label"] = 0

        features["hori_align_to_cell_w_date"] = 0
        features["hori_align_to_cell_w_currency"] = 0
        features["hori_align_to_cell_w_address"] = 0
        features["hori_align_to_cell_w_datelabel"] = 0
        features["hori_align_to_cell_w_dateofinvoicelabel"] = 0
        features["hori_align_to_cell_w_numlabel"] = 0
        features["hori_align_to_cell_w_totallabel"] = 0
        features["hori_align_to_cell_w_digit"] = 0
        features["hori_align_to_cell_w_invoicenum_label"] = 0
        features["hori_align_to_cell_w_accountnum_label"] = 0
        features["hori_align_to_cell_w_ponum_label"] = 0
        

        for t in invoicePage.grouped_tokens:
            if t is not token:
                if is_vert_aligned(t, token, moe):
                    if t.date_values:
                        features["vert_align_to_cell_w_date"] = 1
                    if t.currency:
                        features["vert_align_to_cell_w_currency"] = 1
                    if t.address:
                        features["vert_align_to_cell_w_address"] = 1
                    if t.date_label:
                        features["vert_align_to_cell_w_datelabel"] = 1
                        if len(t.date_label.split(" ")) > 1: # Process the more specific case of date of invoice label
                            features["vert_align_to_cell_w_dateofinvoicelabel"] = 1 
                    if t.num_label:
                        features["vert_align_to_cell_w_numlabel"] = 1
                        if any(word in t.num_label for word in ["invoice","inv","receipt"]):
                            features["vert_align_to_cell_w_invoicenum_label"] = 1
                        if any(word in t.num_label for word in ["account","acc","customer"]):
                            features["vert_align_to_cell_w_accountnum_label"] = 1
                        if any(word in t.num_label for word in ["po","sales"]):
                            features["vert_align_to_cell_w_ponum_label"] = 1
                    if t.total_label:
                        features["vert_align_to_cell_w_totallabel"] = 1
                    if t.contains_digit:
                        features["vert_align_to_cell_w_digit"] = 1


                if is_hori_aligned(t, token, moe):
                    if t.date_values:
                        features["hori_align_to_cell_w_date"] = 1
                    if t.currency:
                        features["hori_align_to_cell_w_currency"] = 1
                    if t.address:
                        features["hori_align_to_cell_w_address"] = 1
                    if t.date_label:
                        features["hori_align_to_cell_w_datelabel"] = 1
                        if len(t.date_label.split(" ")) > 1: # Process the more specific case of date of invoice label
                            features["hori_align_to_cell_w_dateofinvoicelabel"] = 1 
                    if t.num_label:
                        features["hori_align_to_cell_w_numlabel"] = 1
                        if any(word in t.num_label for word in ["invoice","inv","receipt"]):
                            features["hori_align_to_cell_w_invoicenum_label"] = 1
                        if any(word in t.num_label for word in ["account","acc","customer"]):
                            features["hori_align_to_cell_w_accountnum_label"] = 1
                        if any(word in t.num_label for word in ["po","sales"]):
                            features["hori_align_to_cell_w_ponum_label"] = 1
                    if t.total_label:
                        features["hori_align_to_cell_w_totallabel"] = 1
                    if t.contains_digit:
                        features["hori_align_to_cell_w_digit"] = 1
                    

        # dist to nearest cell with field (inf if no field in page)
        features["dist_nearest_cell_w_date"] = 99999#math.inf
        features["dist_nearest_cell_w_currency"] = 99999#math.inf
        features["dist_nearest_cell_w_address"] = 99999#math.inf
        features["dist_nearest_cell_w_datelabel"] = 99999#math.inf
        features["dist_nearest_cell_w_numlabel"] = 99999#math.inf
        features["dist_nearest_cell_w_totallabel"] = 99999#math.inf
        features["dist_nearest_cell_w_digit"] = 99999#math.inf

        for t in invoicePage.grouped_tokens:
            if t is not token:
                dist = calc_min_dist(t, token)
                if t.date_values and dist < features["dist_nearest_cell_w_date"]:
                    features["dist_nearest_cell_w_date"] = dist
                if t.currency and dist < features["dist_nearest_cell_w_currency"]:
                    features["dist_nearest_cell_w_currency"] = dist
                if t.address and dist < features["dist_nearest_cell_w_address"]:
                    features["dist_nearest_cell_w_address"] = dist
                if t.date_label and dist < features["dist_nearest_cell_w_datelabel"]:
                    features["dist_nearest_cell_w_datelabel"] = dist
                if t.num_label and dist < features["dist_nearest_cell_w_numlabel"]:
                    features["dist_nearest_cell_w_numlabel"] = dist
                if t.total_label and dist < features["dist_nearest_cell_w_totallabel"]:
                    features["dist_nearest_cell_w_totallabel"] = dist
                if t.contains_digit and dist < features["dist_nearest_cell_w_digit"]:
                    features["dist_nearest_cell_w_digit"] = dist

        features["rel_dist_nearest_cell_w_date"] = (
            features["dist_nearest_cell_w_date"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_currency"] = (
            features["dist_nearest_cell_w_currency"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_address"] = (
            features["dist_nearest_cell_w_address"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_datelabel"] = (
            features["dist_nearest_cell_w_datelabel"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_numlabel"] = (
            features["dist_nearest_cell_w_numlabel"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_totallabel"] = (
            features["dist_nearest_cell_w_totallabel"] / invoice_diag
        )
        features["rel_dist_nearest_cell_w_digit"] = (
            features["dist_nearest_cell_w_digit"] / invoice_diag
        )

        """
        features TODO:
    
        -text in bold (contains, aligns, dist)
        -text from an area that was shaded
        -token was from a grid (can be close to grid lines or q far away in a well spaced out grid box) / near a summation line (above total payable amounts)
        -percentage of black pixels in box?
        """

        return features

    @classmethod
    def create_min_distance_feature(self, token: Token, target_tokens: List[Token]):
        """Returns a float which represents the min distance from the token to any of the tokens in the target_tokens list"""
        min_distance = float("inf")
        for target_token in target_tokens:
            distance = token.get_distance_to(target_token)
            if distance < min_distance:
                min_distance = distance
        return min_distance

    @classmethod
    def create_alignment_feature(self, token: Token, target_tokens: List[Token]):
        """Returns a boolean according to whether the token aligns to any of the tokens provided in the target_tokens list"""
        return any(list(map(token.is_aligned_with, target_tokens)))

